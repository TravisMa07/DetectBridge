package io.detectbridge.detection;

import java.util.List;

/** Fixed runtime boundaries, not operator-supplied topic templates. */
enum DetectionMode {
  LEGACY("v1"), MAPPED("v2");
  final String suffix;
  final String input;
  final String output;
  final String quarantine;
  final List<String> topics;

  DetectionMode(String suffix) {
    this.suffix = suffix;
    input = "detectbridge.detection.input." + suffix;
    output = "detectbridge.detection.results." + suffix;
    quarantine = "detectbridge.detection.quarantine." + suffix;
    topics = List.of(input, output, quarantine);
  }

  void require(Evaluator evaluator) {
    if (this == LEGACY) evaluator.requireLegacyDeployment();
    else evaluator.requireMappedDeployment();
  }

  String binding(Evaluator evaluator, String cluster, String group, java.util.Map<String, String> topics) {
    if (this == LEGACY) return BundleBinding.fingerprint(evaluator.bundle(), cluster, group, topics);
    return BundleBinding.fingerprint(evaluator.bundle(), evaluator.semanticVersion() + "/" + Evaluator.SELECTION_VERSION,
        cluster, group, topics);
  }
}
