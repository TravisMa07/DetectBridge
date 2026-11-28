package io.detectbridge.integration;

import static io.detectbridge.detection.Contracts.check;
import static io.detectbridge.integration.LifecycleSupport.*;
import java.io.*;
import java.time.*;
import java.util.*;
import java.util.concurrent.*;
import org.apache.flink.api.connector.source.*;
import org.apache.flink.core.io.*;
import org.apache.kafka.clients.consumer.*;
import org.apache.kafka.common.TopicPartition;
import tools.jackson.databind.JsonNode;

/** One checkpointed reader arbitrates raw admission without blocking administrative polling. */
public final class LifecycleSource implements Source<LifecycleWorker.Delivery,LifecycleSource.WorkerSplit,Boolean> {
  private final byte[] config;private final LifecycleHooks hooks;
  public LifecycleSource(JsonNode config){this(config,LifecycleHooks.NONE);}
  public LifecycleSource(JsonNode config,LifecycleHooks hooks){this.config=bytes(config);this.hooks=hooks;}
  public record WorkerSplit(String splitId,byte[] snapshot) implements SourceSplit {public WorkerSplit {snapshot=snapshot==null?null:snapshot.clone();}@Override public byte[] snapshot(){return snapshot==null?null:snapshot.clone();}}
  public Boundedness getBoundedness(){return Boundedness.CONTINUOUS_UNBOUNDED;}
  public SourceReader<LifecycleWorker.Delivery,WorkerSplit> createReader(SourceReaderContext context)throws Exception {check(context.currentParallelism()==1&&context.getIndexOfSubtask()==0,"lifecycle_reader_topology");return new Reader(parse(config,RECORD),hooks);}
  public SplitEnumerator<WorkerSplit,Boolean> createEnumerator(SplitEnumeratorContext<WorkerSplit> context){return new Enumerator(context,false);}
  public SplitEnumerator<WorkerSplit,Boolean> restoreEnumerator(SplitEnumeratorContext<WorkerSplit> context,Boolean assigned){return new Enumerator(context,assigned);}
  static WorkerSplit snapshotSplit(String workerId,LifecycleWorker worker,long checkpoint,LifecycleHooks hooks)throws Exception {
    byte[] snapshot=worker.snapshot(checkpoint);
    hooks.afterSnapshot(checkpoint,!worker.ready||worker.machine==null?null:worker.machine.selection(),io.detectbridge.transport.Json.sha(snapshot));
    return new WorkerSplit(workerId,snapshot);
  }
  public SimpleVersionedSerializer<WorkerSplit> getSplitSerializer(){return new SimpleVersionedSerializer<>() {
    public int getVersion(){return 1;}
    public byte[] serialize(WorkerSplit split)throws IOException {ByteArrayOutputStream bytes=new ByteArrayOutputStream();try(var out=new DataOutputStream(bytes)){out.writeUTF(split.splitId());byte[] state=split.snapshot();out.writeInt(state==null?-1:state.length);if(state!=null)out.write(state);}return bytes.toByteArray();}
    public WorkerSplit deserialize(int version,byte[] bytes)throws IOException {check(version==1&&bytes.length<=STATE_BYTES+128,"lifecycle_split_version");try(var in=new DataInputStream(new ByteArrayInputStream(bytes))){String id=in.readUTF();int length=in.readInt();check(length>=-1&&length<=STATE_BYTES,"lifecycle_split_limit");byte[] state=length<0?null:in.readNBytes(length);check((state==null||state.length==length)&&in.available()==0,"lifecycle_split_encoding");return new WorkerSplit(id,state);}}
  };}
  public SimpleVersionedSerializer<Boolean> getEnumeratorCheckpointSerializer(){return new SimpleVersionedSerializer<>() {
    public int getVersion(){return 1;}public byte[] serialize(Boolean value){return new byte[]{(byte)(value?1:0)};}public Boolean deserialize(int version,byte[] bytes){check(version==1&&bytes.length==1&&(bytes[0]==0||bytes[0]==1),"lifecycle_enumerator_version");return bytes[0]==1;}
  };}
  final class Enumerator implements SplitEnumerator<WorkerSplit,Boolean> {
    final SplitEnumeratorContext<WorkerSplit> context;boolean assigned;
    Enumerator(SplitEnumeratorContext<WorkerSplit> context,boolean assigned){this.context=context;this.assigned=assigned;check(context.currentParallelism()==1,"lifecycle_enumerator_topology");}
    public void start(){}public void handleSplitRequest(int reader,String host){addReader(reader);}public void addReader(int reader){check(reader==0,"lifecycle_reader_id");if(!assigned){assigned=true;context.assignSplit(new WorkerSplit(parse(config,RECORD).get("worker_id").asString(),null),0);context.signalNoMoreSplits(0);}}
    public void addSplitsBack(List<WorkerSplit> splits,int reader){check(false,"lifecycle_explicit_replacement_required");}public Boolean snapshotState(long checkpoint){return assigned;}public void close(){}
  }
  public static final class Reader implements SourceReader<LifecycleWorker.Delivery,WorkerSplit> {
    final JsonNode config;final LifecycleHooks hooks;LifecycleWorker worker;KafkaConsumer<byte[],byte[]> consumer;boolean split,closed;ConsumerRecord<byte[],byte[]> pending,pendingAdmin;
    final ScheduledExecutorService timer=Executors.newSingleThreadScheduledExecutor(r->{Thread t=new Thread(r,"lifecycle-availability");t.setDaemon(true);return t;});
    CompletableFuture<Void> available=CompletableFuture.completedFuture(null);
    Reader(JsonNode config,LifecycleHooks hooks){this.config=config;this.hooks=hooks;}
    public void start(){}
    TopicPartition part(String role){return new TopicPartition(config.at("/topics/"+role+"/name").asString(),0);}
    public void addSplits(List<WorkerSplit> splits){try{check(!split&&splits.size()==1&&splits.get(0).splitId().equals(config.get("worker_id").asString()),"lifecycle_duplicate_split");split=true;LifecycleTool.verifyBroker(config);worker=new LifecycleWorker(config,Clock.systemUTC());if(splits.get(0).snapshot()!=null)worker.restore(splits.get(0).snapshot());consumer=new KafkaConsumer<>(LifecycleTool.consumer(config.get("bootstrap").asString(),config.get("consumer_group").asString()));var parts=List.of(part("input"),part("control"),part("artifact"));consumer.assign(parts);var earliest=consumer.beginningOffsets(parts);var ends=consumer.endOffsets(parts);for(String role:List.of("input","control","artifact")){long next=role.equals("input")?worker.rawNext:role.equals("control")?worker.controlNext:worker.artifactNext;check(next>=earliest.get(part(role))&&next<=ends.get(part(role)),"lifecycle_preservation_gap");consumer.seek(part(role),next);}available.complete(null);}catch(Exception e){throw new IllegalStateException("lifecycle_reader_initialize",e);}}
    public InputStatus pollNext(ReaderOutput<LifecycleWorker.Delivery> output)throws Exception {
      if(!split)return InputStatus.NOTHING_AVAILABLE;
      worker.release(output::collect,hooks.holdRelease());worker.pump();
      if(pendingAdmin!=null&&processAdmin(pendingAdmin))pendingAdmin=null;
      for(String role:List.of("control","artifact")){if(pendingAdmin!=null&&pendingAdmin.topic().equals(part(role).topic()))consumer.pause(List.of(part(role)));else consumer.resume(List.of(part(role)));}
      if(pending!=null&&worker.canAdmit(pending.value())){worker.raw(pending.value(),pending.offset());pending=null;worker.pump();}
      boolean pause=pending!=null||!worker.ready||worker.machine==null||!worker.machine.canAdmit(2*MIB);
      if(pause)consumer.pause(List.of(part("input")));else consumer.resume(List.of(part("input")));
      var records=consumer.poll(Duration.ZERO);check(records.count()<=1,"lifecycle_poll_bound");for(var row:records){
        if(row.topic().equals(part("input").topic())){check(row.value()==null||row.value().length<=2*MIB,"lifecycle_raw_size_blocked");if(worker.canAdmit(row.value())){worker.raw(row.value(),row.offset());worker.pump();}else pending=row;}
        else {if(!processAdmin(row)){check(pendingAdmin==null,"lifecycle_pending_admin_limit");pendingAdmin=row;}}
      }
      worker.release(output::collect,hooks.holdRelease());worker.pump();
      available=new CompletableFuture<>();CompletableFuture<Void> wake=available;timer.schedule(()->wake.complete(null),500,TimeUnit.MILLISECONDS);return InputStatus.NOTHING_AVAILABLE;
    }
    boolean processAdmin(ConsumerRecord<byte[],byte[]> row)throws Exception {
      String role=row.topic().equals(part("control").topic())?"control":"artifact";
      try{check(row.value()!=null,"lifecycle_null_control");if(role.equals("control"))worker.control(row.value(),row.offset()+1);else worker.artifact(row.value(),row.offset()+1);return true;}
      catch(LifecycleValidator.Unavailable pending){return false;}
      catch(IllegalArgumentException invalid){String category=invalid.getMessage();check(category!=null&&protocolRejection(category),"lifecycle_unclassified_rejection");worker.rejected(role,row.offset(),row.key(),row.value(),category);return true;}
    }
    static boolean protocolRejection(String category) {
      return category.startsWith("lifecycle_schema_")||Set.of("lifecycle_invalid_json","lifecycle_integer_syntax","lifecycle_null_control","lifecycle_control_limit","lifecycle_control_scope","lifecycle_control_order","lifecycle_control_conflict","lifecycle_observed_gap","lifecycle_proposal_scope","lifecycle_proposal_reuse","lifecycle_registration_order","lifecycle_registration_membership","lifecycle_registration_input","lifecycle_run_order","lifecycle_run_reassignment","lifecycle_run_exhausted","lifecycle_rollback_target","lifecycle_membership_target","lifecycle_signing_key","lifecycle_invalid_signature","lifecycle_signature_size","lifecycle_base64","lifecycle_public_key_encoding","lifecycle_artifact_limit","lifecycle_artifact_scope","lifecycle_transfer_busy","lifecycle_chunk_integrity","lifecycle_chunk_conflict","lifecycle_chunk_metadata","lifecycle_installed_chunk_conflict","lifecycle_member_integrity","lifecycle_bundle_hash","lifecycle_bundle_plan","lifecycle_bundle_profile","lifecycle_invalid_bundle","lifecycle_compiler_mismatch").contains(category);
    }
    public List<WorkerSplit> snapshotState(long checkpoint){try{check(split,"lifecycle_missing_split");LifecycleTool.verifyBroker(config);return List.of(snapshotSplit(config.get("worker_id").asString(),worker,checkpoint,hooks));}catch(Exception failure){throw new IllegalStateException("lifecycle_checkpoint_failed",failure);}}
    public void notifyCheckpointComplete(long id){if(worker!=null)worker.completed(id);available.complete(null);}
    public void notifyCheckpointAborted(long id){if(worker!=null)worker.aborted(id);available.complete(null);}
    public CompletableFuture<Void> isAvailable(){return available;}
    public void notifyNoMoreSplits(){}
    public void close()throws Exception {closed=true;timer.shutdownNow();available.complete(null);if(consumer!=null)consumer.close(Duration.ofSeconds(10));if(worker!=null)worker.close();}
  }
}
