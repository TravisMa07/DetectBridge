package io.detectbridge.integration;

import static io.detectbridge.detection.Contracts.check;
import static io.detectbridge.integration.LifecycleSupport.*;
import java.nio.file.*;
import java.util.*;
import tools.jackson.databind.JsonNode;

/** Separate probe artifact: no configuration value can select these production fault hooks. */
public final class LifecycleQualificationJob {
  static final class Probe implements LifecycleHooks {
    final String mode,root,outputTopic,incarnation;Probe(String mode,String root,String outputTopic,String incarnation){this.mode=mode;this.root=root;this.outputTopic=outputTopic;this.incarnation=incarnation;}
    public boolean holdRelease(){return mode.equals("hold-release")&&!Files.exists(Path.of(root,"release"));}
    public void afterSnapshot(long checkpoint,JsonNode selection,String snapshotSha256)throws Exception {
      if(selection==null||!selection.path("origin_incarnation").asString().equals(incarnation)||!mode.equals("checkpoint-timeout")||Files.exists(Path.of(root,"snapshot-start.json")))return;
      publish(Path.of(root,"snapshot-start.json"),bytes(value(Map.of("checkpoint_id",checkpoint,"selection",selection,"snapshot_sha256",snapshotSha256))));
      long until=System.nanoTime()+java.time.Duration.ofSeconds(65).toNanos();while(!Files.exists(Path.of(root,"release"))&&System.nanoTime()<until)Thread.sleep(100);
    }
    public void afterSinkAck(String topic,long offset,String key,String hash)throws Exception {
      if(!mode.equals("partial-sink")||!topic.equals(outputTopic)||Files.exists(Path.of(root,"sink-ack.json")))return;
      publish(Path.of(root,"sink-ack.json"),bytes(value(Map.of("topic",topic,"offset",offset,"key",key,"value_sha256",hash))));throw new java.io.IOException("lifecycle_qualification_after_actual_ack");
    }
  }
  public static void main(String[] args)throws Exception {check(args.length==4&&Set.of("hold-release","checkpoint-timeout","partial-sink").contains(args[1]),"lifecycle_probe_arguments");codeSource(LifecycleQualificationJob.class,args[3]);java.util.UUID.fromString(args[2]);JsonNode config=parse(read(Path.of(args[0]),RECORD),RECORD);Path root=Path.of(config.get("store_root").asString(),"probes",args[2]);privatePath(root,true);LifecycleJob.run(new String[]{args[0]},new Probe(args[1],root.toString(),config.at("/topics/output/name").asString(),config.get("incarnation").asString()));}
}
