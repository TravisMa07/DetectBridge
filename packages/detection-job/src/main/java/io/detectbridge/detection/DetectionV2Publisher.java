package io.detectbridge.detection;

/** Private helper with the same explicit v2 topic boundary as the job. */
public final class DetectionV2Publisher {
  public static void main(String[] args) {
    DetectionPublisher.execute(args, DetectionMode.MAPPED);
  }
}
