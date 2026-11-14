package io.detectbridge.detection;

import io.detectbridge.transport.Json;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/** Checkpoint compatibility includes the active bundle and frozen Kafka configuration. */
public final class BundleBinding {
  private BundleBinding() {}

  public static String fingerprint(
      String bundle, String cluster, String group, Map<String, String> topics) {
    return Json.sha(
        Json.bytes(List.of(bundle, Evaluator.VERSION, cluster, group, new TreeMap<>(topics))));
  }

  public static void requireRestored(String expected, Iterable<String> state) {
    int count = 0;
    for (String value : state) {
      Contracts.check(expected.equals(value), "incompatible_detection_restore");
      count++;
    }
    Contracts.check(count == 1, "missing_or_ambiguous_detection_binding");
  }
}
