package io.detectbridge.integration;

import java.io.Serializable;
import tools.jackson.databind.JsonNode;

/** Only first-party qualification entry points supply hooks; production always uses NONE. */
public interface LifecycleHooks extends Serializable {
  LifecycleHooks NONE=new LifecycleHooks(){};
  default boolean holdRelease(){return false;}
  default void afterSnapshot(long checkpoint,JsonNode selection,String snapshotSha256)throws Exception {}
  default void afterSinkAck(String topic,long offset,String key,String valueHash)throws Exception {}
}
