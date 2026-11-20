package io.detectbridge.integration;

import static io.detectbridge.detection.Contracts.check;
import static io.detectbridge.integration.LifecycleSupport.*;
import java.nio.file.Path;
import org.apache.flink.api.common.eventtime.WatermarkStrategy;
import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;

/** Production entry point; fault hooks are not selectable by configuration or candidates. */
public final class LifecycleJob {
  public static void main(String[] args)throws Exception {run(args,LifecycleHooks.NONE);}
  public static void run(String[] args,LifecycleHooks hooks)throws Exception {
    check(args.length==1,"lifecycle_arguments");var config=parse(read(Path.of(args[0]),RECORD),RECORD);LifecycleSupport.config(config);
    codeSource(LifecycleJob.class,config.get("runtime_sha256").asString());codeSource(io.detectbridge.detection.Evaluator.class,PRODUCER);
    check(LifecycleJob.class.getClassLoader()==io.detectbridge.detection.Evaluator.class.getClassLoader()&&LifecycleJob.class.getClassLoader()==LocalEvidence.class.getClassLoader(),"lifecycle_classloader_origin");
    var flink=new org.apache.flink.configuration.Configuration();flink.setString("execution.checkpointing.storage","filesystem");flink.setString("execution.checkpointing.dir","file://"+config.get("state_root").asString()+"/checkpoints");flink.setString("execution.checkpointing.num-retained","3");flink.setString("execution.checkpointing.timeout","60s");flink.setString("execution.checkpointing.externalized-checkpoint-retention","RETAIN_ON_CANCELLATION");flink.setString("restart-strategy.type","none");
    var env=StreamExecutionEnvironment.getExecutionEnvironment(flink);env.setParallelism(1);env.enableCheckpointing(5000);env.getCheckpointConfig().setMaxConcurrentCheckpoints(1);env.getCheckpointConfig().setMinPauseBetweenCheckpoints(1000);
    env.fromSource(new LifecycleSource(config,hooks),WatermarkStrategy.noWatermarks(),"Lifecycle checkpointed worker",TypeInformation.of(LifecycleWorker.Delivery.class)).uid("lifecycle-source-v1").sinkTo(new LifecycleSink(config,hooks)).uid("lifecycle-sink-v1");env.execute("DetectBridge lifecycle worker");
  }
}
