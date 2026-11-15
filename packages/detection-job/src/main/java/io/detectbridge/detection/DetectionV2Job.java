package io.detectbridge.detection;

/** Explicit v2 topics/state; never adopts the P09 deployment. */
public final class DetectionV2Job {
  public static void main(String[] args) throws Exception {
    DetectionJob.run(args, DetectionMode.MAPPED);
  }
}
