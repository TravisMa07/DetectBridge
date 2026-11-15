# Opt-in local recording catalog

Version-1 manifests here describe reviewed local controlled recordings, with real
consumers in the owning adapter's qualification tool. They are distinct from
P04's public-download dataset manifests; the existing P04 registry/schema stays
unchanged. No payload, binary, password or private key belongs in this directory.

`openssh9-password-lab-v1.json` pins a small real loopback OpenSSH9 recording,
original native messages, collector framing, actual image/container/binary/package
metadata, reviewed host/generation context, local-use terms and independent
per-record expectations. Payloads are retained only in ignored local cache.
The Linux gate validates committed catalog/capture attribution; opt-in
`packages/linux-adapters/recording/qualify.py` rehashes every original artifact and
checks all adapter/evaluator outputs. Ordinary CI runs synthetic boundary and
verifier regressions and does not claim replay of an absent local recording.

A new capture has new timestamps, ports and identity. It must receive a new
manifest/review; it cannot replace bytes under this immutable recording ID.
Public payload distribution requires its own owner provenance/terms decision.
