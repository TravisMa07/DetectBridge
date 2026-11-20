"""Ephemeral, first-party qualification artifact preparation; no effective control."""

import contextlib
import copy
import functools

import lifecycle as local
import lifecycle_diagnostics as diagnostic
import lifecycle_validation as candidate

encoded, sha = candidate.encoded, candidate.sha
_INTERNAL = object()


def require(condition):
    if not condition:
        raise ValueError("lifecycle_runtime_qualification_artifact_preparation")


def invalidate(runtime):
    cap = getattr(runtime, "_qualification_artifact_preparation", None)
    if cap is not None:
        cap["invalid"] = True


def invalidate_on_error(function):
    @functools.wraps(function)
    def guarded(runtime, *args, **kwargs):
        try:
            return function(runtime, *args, **kwargs)
        except BaseException:
            invalidate(runtime)
            raise

    return guarded


def invalidate_after_change(function):
    @functools.wraps(function)
    def guarded(runtime, *args, **kwargs):
        try:
            return function(runtime, *args, **kwargs)
        finally:
            invalidate(runtime)

    return guarded


def capability(runtime, token=_INTERNAL):
    cap = runtime._qualification_artifact_preparation
    require(
        cap is not None and not cap["invalid"] and (token is _INTERNAL or token is cap["token"])
    )
    return cap


def job_identity(job):
    if job is None:
        return None
    # checkpoints() journals the rolling set of completed restore paths during
    # ordinary observations. It does not change the running job/incarnation.
    return {
        key: copy.deepcopy(value) for key, value in job.items() if key != "completed_restore_paths"
    }


def context(runtime, registrations):
    current = runtime.state["publications"][-1]
    stat = runtime.root.stat()
    return dict(
        root=[str(runtime.root), stat.st_dev, stat.st_ino],
        config=runtime.config,
        broker=runtime.state["broker"],
        workers={r["worker_id"]: runtime.state["workers"][r["worker_id"]] for r in registrations},
        jobs={
            r["worker_id"]: job_identity(runtime.state["jobs"].get(r["worker_id"]))
            for r in registrations
        },
        revision=current["revision"],
        command_sha256=current["command_sha256"],
    )


def check_context(runtime, cap):
    require(
        not cap["invalid"]
        and sha(encoded(context(runtime, cap["registrations"]))) == cap["context_sha256"]
    )


def evidence(cap, name, value):
    data = encoded(value)
    require(len(data) <= 65536)
    local.write_exclusive(cap["evidence"] / name, data)
    return sha(data)


def original_proof(cap, label, proof):
    data = encoded(proof)
    require(len(data) <= 2 * 1024 * 1024 + 65536)
    digest = sha(data)
    if digest not in cap["original_proofs"]:
        require(
            len(cap["original_proofs"]) < 64
            and cap["original_proof_bytes"] + len(data) <= 32 * 1024 * 1024
        )
        local.write_exclusive(cap["evidence"] / (label + "-" + digest + ".json"), data)
        cap["original_proofs"].add(digest)
        cap["original_proof_bytes"] += len(data)
    return digest


def observation(runtime, worker, checkpoint, inventory):
    """Called only after ordinary Runtime.worker_inventory's real COMPLETED checks."""
    cap = getattr(runtime, "_qualification_artifact_preparation", None)
    if cap is None or cap["invalid"] or cap["phase"] not in ("prepared", "ready"):
        return
    require(worker in cap["jobs"])
    require(job_identity(runtime.state["jobs"][worker]) == cap["jobs"][worker])
    require(
        checkpoint.get("status") == "COMPLETED" and checkpoint["id"] == inventory["checkpoint_id"]
    )
    group = None
    expected = cap["expected_group"]
    if worker == expected["worker_id"]:
        for candidate_group in inventory.get("machine", {}).get("groups", []):
            if candidate_group.get("key") == expected["key"]:
                members = candidate_group.get("members", [])
                if len(members) == 5 and sorted(members, key=lambda r: r["record_id"]) == sorted(
                    expected["members"], key=lambda r: r["record_id"]
                ):
                    require(
                        type(candidate_group.get("opened")) is int
                        and candidate_group.get("deadline") - candidate_group["opened"] == 30000
                    )
                    group = dict(
                        opened=candidate_group["opened"],
                        deadline=candidate_group["deadline"],
                        sha256=sha(encoded(candidate_group)),
                    )
    cap["observations"][worker] = dict(
        checkpoint_id=checkpoint["id"],
        snapshot_sha256=inventory["snapshot_sha256"],
        selection=copy.deepcopy(inventory["selection"]),
        artifact_cursor=copy.deepcopy(inventory["artifact_cursor"]),
        rejection_head=copy.deepcopy(inventory["rejection_head"]),
        group=group,
    )


def current_observation(runtime, cap, worker, row, minimum):
    selected = row["selection"] or {}
    if (
        selected.get("revision") != cap["expected_revision"]
        or selected.get("command_sha256") != cap["expected_hash"]
    ):
        return False
    require(selected.get("origin_incarnation") == cap["incarnations"][worker])
    cursor = row["artifact_cursor"]
    require(
        cursor["cluster_id"] == cap["broker"]["cluster_id"]
        and cursor["topic"] == cap["broker"]["topics"]["artifact"]
        and type(cursor["next_offset"]) is int
        and cursor["next_offset"] >= 0
    )
    baseline = cap["baseline"][worker]
    if row["checkpoint_id"] < baseline["checkpoint_id"]:
        return False
    require(row["rejection_head"] == baseline["rejection_head"])
    return cursor["next_offset"] >= minimum


@contextlib.contextmanager
def scope(
    runtime,
    store,
    proposal,
    registrations,
    expected_revision,
    expected_hash,
    *,
    expected_open_group,
    evidence_root,
):
    require(runtime.config.get("qualification_sha256") is not None)
    if runtime._qualification_artifact_preparation is not None:
        invalidate(runtime)
        require(False)
    require(
        isinstance(expected_open_group, dict)
        and set(expected_open_group) == {"worker_id", "key", "members"}
        and len(expected_open_group["members"]) == 5
        and len({r["record_id"] for r in expected_open_group["members"]}) == 5
        and len(encoded(expected_open_group)) <= 65536
    )
    folder = local.path_safe(evidence_root)
    local.disjoint(folder, runtime.root)
    local.disjoint(folder, store.root)
    require(not folder.exists() and folder.parent.is_dir())
    folder.mkdir(mode=0o700)
    token = object()
    cap = dict(
        token=token,
        invalid=False,
        phase="initial",
        evidence=folder,
        expected_group=copy.deepcopy(expected_open_group),
        registrations=copy.deepcopy(registrations),
        expected_revision=expected_revision,
        expected_hash=expected_hash,
        baseline={},
        observations={},
        ready={},
        receipts=[],
        original_proofs=set(),
        original_proof_bytes=0,
    )
    runtime._qualification_artifact_preparation = cap
    try:
        with diagnostic.span("artifact_preparation", runtime):
            # Baselines and later readiness use actual independent completed inventories,
            # outside the30s group. No caller may submit a purported proof/receipt.
            for registration in registrations:
                worker = registration["worker_id"]
                cp = runtime.checkpoints(worker).get("latest", {}).get("completed")
                require(cp is not None and cp.get("status") == "COMPLETED")
                proof = runtime.worker_inventory(worker, cp["id"])
                selected = proof["inventory"].get("selection") or {}
                require(
                    selected.get("revision") == expected_revision
                    and selected.get("command_sha256") == expected_hash
                    and selected.get("origin_incarnation") == registration["incarnation"]
                )
                cap["baseline"][worker] = dict(
                    checkpoint_id=cp["id"],
                    rejection_head=copy.deepcopy(proof["inventory"]["rejection_head"]),
                    job=job_identity(runtime.state["jobs"][worker]),
                    original_sha256=original_proof(cap, "baseline", proof),
                )
                evidence(cap, "baseline-" + worker + ".json", cap["baseline"][worker])
            with store._locked(), runtime._locked():
                store._load()
                runtime._load()
                require(expected_open_group["worker_id"] in cap["baseline"])
                cap["jobs"] = copy.deepcopy(
                    {
                        r["worker_id"]: job_identity(runtime.state["jobs"].get(r["worker_id"]))
                        for r in registrations
                    }
                )
                require(all(job is not None and job.get("job_id") for job in cap["jobs"].values()))
                require(
                    all(
                        cap["jobs"][worker] == cap["baseline"][worker]["job"]
                        for worker in cap["jobs"]
                    )
                )
                cap["incarnations"] = {r["worker_id"]: r["incarnation"] for r in registrations}
                cap["context_sha256"] = sha(encoded(context(runtime, registrations)))
                cap["broker"] = copy.deepcopy(runtime.state["broker"])
                cap["proposal_sha256"] = sha(encoded(proposal))
                cap["store"] = [str(store.root), store.root.stat().st_dev, store.root.stat().st_ino]
                runtime._publish_locked(
                    store,
                    proposal,
                    registrations,
                    expected_revision,
                    expected_hash,
                    _qualification_prepare=True,
                )
                require(cap["receipts"])
                cap["artifact_next"] = max(r["offset"] for r in cap["receipts"]) + 1
                cap["phase"] = "prepared"
        yield token
    except BaseException:
        invalidate(runtime)
        raise
    finally:
        cap["invalid"] = True
        cap["observations"].clear()
        cap["ready"].clear()
        runtime._qualification_artifact_preparation = None


@diagnostic.measured("artifact_readiness")
def readiness(runtime, token):
    cap = capability(runtime, token)
    require(cap["phase"] in ("prepared", "ready"))
    with runtime._locked():
        runtime._load()
        check_context(runtime, cap)
    for worker in cap["jobs"]:
        cp = runtime.checkpoints(worker).get("latest", {}).get("completed")
        if cp is None or cp.get("status") != "COMPLETED":
            return None
        proof = runtime.worker_inventory(worker, cp["id"])
        row = cap["observations"][worker]
        if not current_observation(runtime, cap, worker, row, cap["artifact_next"]):
            return None
        row["original_sha256"] = original_proof(cap, "readiness", proof)
        cap["ready"][worker] = copy.deepcopy(row)
    cap["phase"] = "ready"
    return dict(
        artifact_next=cap["artifact_next"],
        workers={
            w: dict(
                checkpoint_id=r["checkpoint_id"],
                snapshot_sha256=r["snapshot_sha256"],
                proof_sha256=r["original_sha256"],
            )
            for w, r in cap["ready"].items()
        },
    )


@diagnostic.measured("artifact_authorization")
def authorize(runtime, token, worker, checkpoint_id):
    cap = capability(runtime, token)
    try:
        with runtime._locked():
            runtime._load()
            check_context(runtime, cap)
            require(
                cap["phase"] == "ready"
                and set(cap["ready"]) == set(cap["jobs"])
                and worker == cap["expected_group"]["worker_id"]
            )
            row = cap["observations"].get(worker)
            require(
                row is not None
                and row["checkpoint_id"] == checkpoint_id
                and row["group"] is not None
                and row["checkpoint_id"] >= cap["ready"][worker]["checkpoint_id"]
            )
            require(current_observation(runtime, cap, worker, row, cap["artifact_next"]))
            cap["phase"] = "authorized"
            cap["open_proof_sha256"] = evidence(cap, "completed-open-group.json", row)
            return dict(
                checkpoint_id=checkpoint_id,
                proof_sha256=cap["open_proof_sha256"],
                artifact_next=cap["artifact_next"],
            )
    except BaseException:
        invalidate(runtime)
        raise


def before_adoption(runtime, store, proposal, adoption, target):
    cap = capability(runtime)
    check_context(runtime, cap)
    require(
        cap["phase"] == "authorized"
        and cap["proposal_sha256"] == sha(encoded(proposal))
        and cap["adoption_sha256"] == sha(encoded(adoption))
        and cap["store"] == [str(store.root), store.root.stat().st_dev, store.root.stat().st_ino]
        and cap["members"] == member_hashes(target)
    )
    cap["phase"] = "adopting"


def member_hashes(target):
    return {
        name: sha(local.read(target / name, 4 * 1024 * 1024))
        for name in ("manifest.json", "plan.json")
    }


def prepared_transfer(runtime, adoption, target):
    cap = capability(runtime)
    require(cap["phase"] == "initial")
    cap["adoption_sha256"] = sha(encoded(adoption))
    cap["members"] = member_hashes(target)
    runtime._send_artifacts(target, adoption["proposal"]["bundle_sha256"], cap)


def bind_intent(runtime, intent):
    cap = capability(runtime)
    require(
        cap["phase"] == "adopting"
        and "bound_intent" not in cap
        and intent["revision"] == cap["expected_revision"] + 1
        and sha(encoded(intent["control"]["payload"]["proposal"])) == cap["proposal_sha256"]
    )
    cap["bound_intent"] = [sha(encoded(intent)), intent["revision"], intent["command_sha256"]]


def consume(runtime, entry, intent, target):
    cap = getattr(runtime, "_qualification_artifact_preparation", None)
    if cap is None:
        return False
    capability(runtime)
    require(
        cap["phase"] == "adopting"
        and cap.get("bound_intent")
        == [entry["intent_sha256"], entry["revision"], entry["command_sha256"]]
        and entry["revision"] == cap["expected_revision"] + 1
        and entry["adoption_sha256"] == cap["adoption_sha256"]
        and entry["intent_sha256"] == sha(encoded(intent))
        and intent["command_sha256"] == entry["command_sha256"]
        and sha(encoded(intent["control"]["payload"]["proposal"])) == cap["proposal_sha256"]
        and cap["members"] == member_hashes(target)
    )
    cap["phase"] = "consumed"
    evidence(
        cap,
        "consumed-intent.json",
        dict(
            revision=entry["revision"],
            intent_sha256=entry["intent_sha256"],
            command_sha256=entry["command_sha256"],
        ),
    )
    return True
