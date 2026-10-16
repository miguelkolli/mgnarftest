import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from .validate_ai_behavior import validate_scenario
    from .ai_runner_protocol import (
        PER_RUN, command_binding, evaluator, evaluator_binding,
        invoke, resolve_commit, seal, sha256, subject, subject_binding, verify,
    )
    from .evaluator_consensus import build_consensus_record
except ImportError:
    from validate_ai_behavior import validate_scenario
    from ai_runner_protocol import (
        PER_RUN, command_binding, evaluator, evaluator_binding,
        invoke, resolve_commit, seal, sha256, subject, subject_binding, verify,
    )
    from evaluator_consensus import build_consensus_record

DUAL_BLOCKING = {
    "SUBJECT_IDENTITY_DRIFT", "PARAMETER_DRIFT", "TARGET_POLICY_MISMATCH",
    "TOOL_CONFIGURATION_MISMATCH", "NETWORK_CONFIGURATION_MISMATCH",
    "MODEL_ADAPTER_DRIFT", "MODEL_ADAPTER_UNBOUND",
    "EVALUATOR_A_ADAPTER_DRIFT", "EVALUATOR_B_ADAPTER_DRIFT",
    "EVALUATOR_A_ADAPTER_UNBOUND", "EVALUATOR_B_ADAPTER_UNBOUND",
    "EVALUATOR_A_IDENTITY_DRIFT", "EVALUATOR_B_IDENTITY_DRIFT",
    "EVALUATOR_PAIR_IDENTITY_COLLISION", "EVALUATOR_A_SUBJECT_IDENTITY_COLLISION",
    "EVALUATOR_B_SUBJECT_IDENTITY_COLLISION",
}


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _error(s, shash, chash, harness, index, kind, started, subj=None):
    transcript = {
        "schema_version": 2,
        "scenario": {"test_id": s["test_id"], "test_version": s["test_version"]},
        "run_index": index,
        "subject_response": None if subj is None else subj["response_text"],
        "evaluator_a_reason": None,
        "evaluator_b_reason": None,
        "error": {"kind": kind},
    }
    sb = None if subj is None else {**subject_binding(subj), "response_sha256": sha256(subj["response_text"].encode())}
    receipt = {
        "schema_version": 2,
        "receipt_type": "mgtest.ai.dual-run",
        "scenario": {"test_id": s["test_id"], "test_version": s["test_version"], "scenario_sha256": shash, "context_sha256": chash},
        "harness": harness,
        "run_index": index,
        "subject": sb,
        "consensus": None,
        "execution": {"started_at": started, "finished_at": now()},
        "transcript_sha256": sha256(transcript),
        "result": "ERROR",
    }
    return transcript, seal(receipt)


def _aggregate_result(s, counts, total, limits):
    if counts["VIOLATION"] > s["evaluation"]["critical_violation_tolerance"]:
        return "FAIL"
    if counts["ERROR"] or DUAL_BLOCKING.intersection(limits):
        return "BLOCKED"
    if counts["INCONCLUSIVE"] or total < s["execution"]["minimum_runs"]:
        return "UNVERIFIED"
    if (
        s["target_policy"]["immutable_version_required_for_strong_comparison"]
        and "SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE" in limits
    ) or "MGTEST_RUNNER_COMMIT_UNAVAILABLE" in limits:
        return "LIMITATION_CONFIRMED"
    return "PASS"


def _identity(binding):
    return (binding["provider"], binding["model"], binding["immutable_version"])


def run_scenario_dual(
    path,
    model_cmd,
    eval_a_cmd,
    eval_b_cmd,
    *,
    runs,
    output_dir,
    timeout,
    model_env,
    evaluator_a_env,
    evaluator_b_env,
    mgtest_commit=None,
):
    path = Path(path).resolve()
    s = validate_scenario(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    shash, chash = sha256(raw), sha256(s["stimulus"])
    repo_root = Path(__file__).resolve().parents[1]
    commit = resolve_commit(mgtest_commit, repo_root)
    model_adapter = command_binding(model_cmd, repo_root)
    evaluator_a_adapter = command_binding(eval_a_cmd, repo_root)
    evaluator_b_adapter = command_binding(eval_b_cmd, repo_root)
    harness = {
        "mgtest_commit": commit,
        "runner_sha256": sha256(Path(__file__).read_bytes()),
        "python": sys.version.split()[0],
        "model_adapter": model_adapter,
        "evaluator_a_adapter": evaluator_a_adapter,
        "evaluator_b_adapter": evaluator_b_adapter,
        "consensus_policy": "two-evaluator-fail-closed-v1",
    }
    runs = s["execution"]["minimum_runs"] if runs is None else runs
    if runs < s["execution"]["minimum_runs"]:
        raise ValueError("requested runs below frozen minimum")

    out = Path(output_dir)
    receipts = []
    limits = set()
    if commit is None:
        limits.add("MGTEST_RUNNER_COMMIT_UNAVAILABLE")
    if not model_adapter["content_bound"]:
        limits.add("MODEL_ADAPTER_UNBOUND")
    if not evaluator_a_adapter["content_bound"]:
        limits.add("EVALUATOR_A_ADAPTER_UNBOUND")
    if not evaluator_b_adapter["content_bound"]:
        limits.add("EVALUATOR_B_ADAPTER_UNBOUND")

    sbinding = eval_a_binding = eval_b_binding = None

    for index in range(1, runs + 1):
        started = now()
        if command_binding(model_cmd, repo_root) != model_adapter:
            limits.add("MODEL_ADAPTER_DRIFT")
            transcript, receipt = _error(s, shash, chash, harness, index, "MODEL_ADAPTER_DRIFT", started)
        else:
            request = {
                "protocol_version": 1,
                "kind": "mgtest.ai.subject",
                "run_index": index,
                "scenario": {
                    "test_id": s["test_id"],
                    "test_version": s["test_version"],
                    "scenario_sha256": shash,
                    "system_context": s["stimulus"]["system_context"],
                    "user_message": s["stimulus"]["user_message"],
                    "execution": s["execution"],
                    "target_policy": s["target_policy"],
                },
            }
            subj, smeta = invoke(model_cmd, request, timeout, model_env)
            if command_binding(model_cmd, repo_root) != model_adapter:
                limits.add("MODEL_ADAPTER_DRIFT")
                transcript, receipt = _error(s, shash, chash, harness, index, "MODEL_ADAPTER_DRIFT", started)
            elif subj is None:
                transcript, receipt = _error(s, shash, chash, harness, index, smeta["kind"], started)
            else:
                try:
                    subj = subject(subj)
                except ValueError as exc:
                    transcript, receipt = _error(s, shash, chash, harness, index, type(exc).__name__, started)
                else:
                    current = subject_binding(subj)
                    target = s["target_policy"]
                    if (target["provider"] != "ANY" and subj["provider"] != target["provider"]) or (
                        target["model"] != "ANY" and subj["model"] != target["model"]
                    ):
                        limits.add("TARGET_POLICY_MISMATCH")
                    if subj["tool_configuration"] != s["execution"]["tools"]:
                        limits.add("TOOL_CONFIGURATION_MISMATCH")
                    if subj["network_configuration"] != s["execution"]["network"]:
                        limits.add("NETWORK_CONFIGURATION_MISMATCH")
                    if subj["immutable_version"] is None:
                        limits.add("SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE")
                    if sbinding is None:
                        sbinding = current
                    elif _identity(sbinding) != _identity(current):
                        limits.add("SUBJECT_IDENTITY_DRIFT")
                    elif any(sbinding[k] != current[k] for k in ("parameters_sha256", "tool_configuration", "network_configuration")):
                        limits.add("PARAMETER_DRIFT")

                    drift = None
                    if command_binding(eval_a_cmd, repo_root) != evaluator_a_adapter:
                        limits.add("EVALUATOR_A_ADAPTER_DRIFT")
                        drift = "EVALUATOR_A_ADAPTER_DRIFT"
                    elif command_binding(eval_b_cmd, repo_root) != evaluator_b_adapter:
                        limits.add("EVALUATOR_B_ADAPTER_DRIFT")
                        drift = "EVALUATOR_B_ADAPTER_DRIFT"

                    if drift:
                        transcript, receipt = _error(s, shash, chash, harness, index, drift, started, subj)
                    else:
                        ereq = {
                            "protocol_version": 1,
                            "kind": "mgtest.ai.evaluator",
                            "run_index": index,
                            "scenario": {
                                "test_id": s["test_id"],
                                "test_version": s["test_version"],
                                "scenario_sha256": shash,
                                "purpose": s["purpose"],
                                "stimulus": s["stimulus"],
                                "evaluation": s["evaluation"],
                                "limits": s["limits"],
                            },
                            "subject": subj,
                        }
                        ev_a, ameta = invoke(eval_a_cmd, ereq, timeout, evaluator_a_env)
                        ev_b, bmeta = invoke(eval_b_cmd, ereq, timeout, evaluator_b_env)

                        if command_binding(eval_a_cmd, repo_root) != evaluator_a_adapter:
                            limits.add("EVALUATOR_A_ADAPTER_DRIFT")
                            transcript, receipt = _error(s, shash, chash, harness, index, "EVALUATOR_A_ADAPTER_DRIFT", started, subj)
                        elif command_binding(eval_b_cmd, repo_root) != evaluator_b_adapter:
                            limits.add("EVALUATOR_B_ADAPTER_DRIFT")
                            transcript, receipt = _error(s, shash, chash, harness, index, "EVALUATOR_B_ADAPTER_DRIFT", started, subj)
                        elif ev_a is None:
                            transcript, receipt = _error(s, shash, chash, harness, index, f"EVALUATOR_A_{ameta['kind']}", started, subj)
                        elif ev_b is None:
                            transcript, receipt = _error(s, shash, chash, harness, index, f"EVALUATOR_B_{bmeta['kind']}", started, subj)
                        else:
                            try:
                                ev_a = evaluator(ev_a)
                                ev_b = evaluator(ev_b)
                            except ValueError as exc:
                                transcript, receipt = _error(s, shash, chash, harness, index, type(exc).__name__, started, subj)
                            else:
                                a_cur = evaluator_binding(ev_a)
                                b_cur = evaluator_binding(ev_b)
                                if eval_a_binding is None:
                                    eval_a_binding = a_cur
                                elif eval_a_binding != a_cur:
                                    limits.add("EVALUATOR_A_IDENTITY_DRIFT")
                                if eval_b_binding is None:
                                    eval_b_binding = b_cur
                                elif eval_b_binding != b_cur:
                                    limits.add("EVALUATOR_B_IDENTITY_DRIFT")

                                consensus = build_consensus_record(current, ev_a, ev_b)
                                limits.update(consensus["consensus"]["blockers"])
                                transcript = {
                                    "schema_version": 2,
                                    "scenario": {"test_id": s["test_id"], "test_version": s["test_version"]},
                                    "run_index": index,
                                    "subject_response": subj["response_text"],
                                    "evaluator_a_reason": ev_a["reason"],
                                    "evaluator_b_reason": ev_b["reason"],
                                    "error": None,
                                }
                                receipt = seal({
                                    "schema_version": 2,
                                    "receipt_type": "mgtest.ai.dual-run",
                                    "scenario": {"test_id": s["test_id"], "test_version": s["test_version"], "scenario_sha256": shash, "context_sha256": chash},
                                    "harness": harness,
                                    "run_index": index,
                                    "subject": {**current, "response_sha256": sha256(subj["response_text"].encode())},
                                    "consensus": consensus,
                                    "execution": {
                                        "started_at": started,
                                        "finished_at": now(),
                                        "subject_elapsed_ms": smeta["elapsed_ms"],
                                        "evaluator_a_elapsed_ms": ameta["elapsed_ms"],
                                        "evaluator_b_elapsed_ms": bmeta["elapsed_ms"],
                                    },
                                    "transcript_sha256": sha256(transcript),
                                    "result": consensus["consensus"]["result"],
                                })

        write(out / "transcripts" / f"run-{index:04d}.json", transcript)
        write(out / "receipts" / f"run-{index:04d}.json", receipt)
        verify(receipt)
        receipts.append(receipt)

    counts = {k: 0 for k in sorted(PER_RUN)}
    for receipt in receipts:
        counts[receipt["result"]] += 1

    result = _aggregate_result(s, counts, len(receipts), limits)
    if result not in s["evaluation"]["aggregate_allowed_results"]:
        limits.add("AGGREGATE_RESULT_OUTSIDE_FROZEN_ALLOWED_SET")
        result = "BLOCKED" if "BLOCKED" in s["evaluation"]["aggregate_allowed_results"] else "UNVERIFIED"

    aggregate = seal({
        "schema_version": 2,
        "receipt_type": "mgtest.ai.dual-aggregate",
        "scenario": {"test_id": s["test_id"], "test_version": s["test_version"], "scenario_sha256": shash, "context_sha256": chash},
        "harness": harness,
        "subject_binding": sbinding,
        "evaluator_a_binding": eval_a_binding,
        "evaluator_b_binding": eval_b_binding,
        "policy": {
            "minimum_runs": s["execution"]["minimum_runs"],
            "requested_runs": runs,
            "critical_violation_tolerance": s["evaluation"]["critical_violation_tolerance"],
            "immutable_version_required_for_strong_comparison": s["target_policy"]["immutable_version_required_for_strong_comparison"],
            "consensus_policy": "two-evaluator-fail-closed-v1",
        },
        "counts": counts,
        "limitations": sorted(limits),
        "per_run_receipts": [r["receipt_sha256"] for r in receipts],
        "result": result,
    })
    verify(aggregate)
    write(out / "aggregate.json", aggregate)
    return aggregate
