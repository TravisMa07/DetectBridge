# Local Kafka, Flink and OpenSearch infrastructure

P06 provides an idle local development stack. It does not run a transport job,
detection, parsing, assembly, API or UI. P07 owns Kafka/Flink delivery semantics.

## Prerequisites and profiles

Use the [development environment](development.md) and an existing Linux Docker
Engine 28+ with Compose 2.32+. The helper does not install or upgrade Docker.
Native Linux ARM64 and AMD64 images are pinned in the
[image lock](../deploy/local/images.lock.json). Host macOS ARM64 runs Linux
containers through Docker Desktop. Windows host development is unqualified.

| Profile | Services | Required Docker memory | Container memory ceilings |
| --- | --- | --- | --- |
| core | Kafka, Flink JobManager and TaskManager | 5 GiB | 4 GiB total |
| full | Core plus OpenSearch | 7 GiB | 6 GiB total |

Kafka has a 1 GiB/1 CPU limit and 512 MiB heap; JobManager 1 GiB/0.5 CPU and
768 MiB process memory; TaskManager 2 GiB/1.5 CPU and 1,536 MiB process memory;
OpenSearch 2 GiB/1.5 CPU and 1 GiB heap. The TaskManager has one slot. These are
initial development bounds, not throughput or job-capacity claims.

Require 10 GiB free on Docker's backing filesystem; warn below 20 GiB. The helper
measures it inside a bounded container, not against the host repository directory.
Full also requires the Docker Linux kernel's `vm.max_map_count` to be at least
262144. `doctor` reports failure without changing the host or Docker VM. On a
Linux host, an administrator can configure this with `sysctl`; on Docker Desktop,
follow its VM-specific configuration guidance. Do not disable bootstrap checks to
hide a missing prerequisite.

Named volumes have no portable hard size quota. Status/preflight checks are
point-in-time checks, not continuous admission control. Kafka time/size expiration
is disabled, so data can fill the disk. Container stdout/stderr logs rotate at
three 10 MiB files each. P16 owns continuous disk-pressure and admission policy.

## Commands

Run these commands from the repository root:

```sh
uv run --locked python tools/stack.py doctor --profile core
uv run --locked python tools/stack.py init --profile core
uv run --locked python tools/stack.py up --profile core
uv run --locked python tools/stack.py status
uv run --locked python tools/stack.py down
```

Full initializes additional volumes and private credentials:

```sh
uv run --locked python tools/stack.py init --profile full
uv run --locked python tools/stack.py up --profile full
```

Global options precede the command: `--project detectbridge-example` selects an
independent deployment and `--port 19200` chooses an alternate OpenSearch loopback
port during its initial configuration. Names must start `detectbridge-` and contain
only lowercase letters, digits and hyphens. Port and image selections are frozen
in state. Use down before switching from full back to core.

The default project is `detectbridge-dev`. Generated state is ignored under
`.cache/stack/<project>/`; named volumes use that project as a prefix. Never copy
state between projects or delete metadata beside retained volumes. Project locks
reject concurrent lifecycle commands. The helper rejects unexpected resource
ownership rather than adopting an existing volume or another application's state.

`init` is idempotent and does not rotate existing credentials or cluster identity.
`up` performs preflight and waits up to 180 seconds for readiness; image pulls and
initialization are separate work. Failures retain development state. `down` removes
containers/network and retains volumes and credentials. It is not a backup.

For deliberate deletion, use the exact project confirmation:

```sh
uv run --locked python tools/stack.py reset --confirm detectbridge-dev
```

This removes only that project's verified volumes and local generated state. It
cannot be undone. Do not run global Docker prune commands as recovery steps.

## Access and security boundary

Kafka and Flink have no host ports and run without listener authentication on a
project-private internal network. Docker administrators and processes they attach
to that network are trusted. This is a local administrative boundary, not an
untrusted multi-tenant network. Do not publish these ports or attach unrelated
containers. A Flink UI/proxy is deferred; readiness inspection uses internal REST
probes. Kafka listens internally at `kafka:9092`, Flink at `jobmanager:8081`.

Full publishes only `https://127.0.0.1:9200`. OpenSearch additionally joins a
project-scoped access bridge because Docker Desktop cannot publish ports from
internal-only networks. Kafka/Flink never join this bridge. OpenSearch therefore
has ordinary bridge outbound connectivity; no egress-blocking claim is made. The security plugin remains enabled;
demo installation and anonymous access are disabled. There are two independently
generated accounts: `operator` for local administration and `health` restricted
to cluster health. Certificate administration has a separate signed admin identity.

The locked OpenSearch image has no OpenSSL executable. Its bundled JDK keytool
creates a private CA and signed node/admin PKCS#12 stores instead; this requires no
host cryptography package or additional image. The CA is valid for ten years and
leaf certificates for 825 days. Initialization does not silently renew or rotate
them. A future expiry/rotation needs a reviewed maintenance procedure.

Private files live in the project's `security/` directory, mode 600 inside a
mode-700 parent. CA/admin private stores remain host-side. The node receives only
its signed store, truststore, public CA, restricted health credential, and security
configuration in a read-only volume. A bounded initializer sets actual Linux
ownership to UID 1000; Compose secret ownership remapping is not assumed. Flink
runs as the pinned image's UID 9999; Kafka and OpenSearch use UID 1000. Application
containers are non-root, have no added capabilities, and use no-new-privileges.

Keep passwords out of command arguments, issues and screenshots. For a local
interactive request, let curl prompt for the operator password; obtain it privately
from the ignored `security/operator-password` file:

```sh
curl --cacert .cache/stack/detectbridge-dev/security/ca.pem \
  --user operator https://127.0.0.1:9200/_cluster/health
```

Verify the CA and hostname. Do not use `-k`. Lifecycle output includes safe
administrative status only; rendered configuration and Docker inspection may
contain credentials and must not be posted publicly.

## Persistence and recovery boundaries

Kafka uses one combined KRaft broker/controller with a persisted cluster ID and
replication factor one. Automatic topic creation is disabled. P06 qualification
creates only disposable synthetic topics; P07 defines application topics.

Flink JobManager and TaskManager share a project volume for `/state/checkpoints`
and `/state/savepoints`. Shared writable-file qualification establishes mount
persistence, not job/checkpoint recovery. This local shared filesystem does not
establish a distributed storage design or JobManager high availability.

OpenSearch uses single-node discovery and its own persistent data volume.
Application indexes and ingestion retry behavior belong to P08. The one-node
stack has no disk-failure protection or host-failure availability guarantee.

Preserve state metadata, credentials, and data volumes together. Missing metadata,
changed Kafka identity, modified credentials, or changed image locks require
explicit recovery review; the helper will not format existing data or generate
replacement credentials automatically. Restore original metadata from backup, or
reset only when the data is intentionally disposable. Image downgrades are not a
migration mechanism. P06 introduces no automatic persisted-state migration or
qualified backup/restore procedure; P21 owns release backup qualification.

For startup failures, inspect `status` and service state first. Common causes are
insufficient Docker memory/disk, an occupied loopback port, a low kernel mapping
limit, missing credentials or filesystem permissions. Existing volumes remain
available after a failed up. Keep infrastructure logs private and remove secrets
before sharing diagnostics.

## Qualification and CI

```sh
uv run --locked python tools/check_stack.py
uv run --locked python tools/stack.py verify --profile core
uv run --locked python tools/stack.py verify --profile full
```

Offline policy validation runs in `tools/dev.py check`. It rejects unpinned images,
unsafe host bindings/mounts, missing limits or health checks, and changed profile
security defaults. Ordinary unit tests use mocks and temporary state.

Runtime verification uses exclusive `detectbridge-test-<uuid>` projects and a
free loopback port. It checks actual limits/users/native architecture/networking,
Kafka synthetic-record persistence, shared Flink state-file persistence, and full
OpenSearch authenticated writes and restart persistence. Missing/wrong credentials
must receive 401; normal requests verify the private CA and hostname. Repeated
initialization must retain metadata exactly. Cleanup removes only its test project,
including on interrupt. SIGKILL or a daemon failure may prevent cleanup; recover
by inspecting the reported test project and resetting that exact project.

Linux AMD64 CI runs both profiles sequentially for deployment/tooling/shared CI
changes. Documentation-only changes skip runtime qualification through explicit
classification. Required aggregate checks reject failed classification, failures,
cancellation and unexpected skipping. No public datasets or application tests are
substituted for infrastructure qualification. Reports include image/runtime versions,
readiness times and observed idle memory; they are not performance acceptance gates.
