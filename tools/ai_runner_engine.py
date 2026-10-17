import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from .validate_ai_behavior import validate_scenario
    from .ai_runner_protocol import (
        BLOCKING, PER_RUN, command_binding, evaluator, evaluator_binding,
        invoke, resolve_commit, seal, sha256, subject, subject_binding, verify,
    )
except ImportError:
    from validate_ai_behavior import validate_scenario
    from ai_runner_protocol import (
        BLOCKING, PER_RUN, command_binding, evaluator, evaluator_binding,
        invoke, resolve_commit, seal, sha256, subject, subject_binding, verify,
    )


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False)+"\n")


def _error(s, shash, chash, harness, index, kind, started, subj=None):
    transcript = {
        "schema_version": 1, "scenario": {"test_id": s["test_id"], "test_version": s["test_version"]},
        "run_index": index, "subject_response": None if subj is None else subj["response_text"],
        "evaluator_reason": None, "error": {"kind": kind},
    }
    sb = None if subj is None else {**subject_binding(subj), "response_sha256": sha256(subj["response_text"].encode())}
    receipt = {
        "schema_version": 1, "receipt_type": "mgtest.ai.run",
        "scenario": {"test_id": s["test_id"], "test_version": s["test_version"], "scenario_sha256": shash, "context_sha256": chash},
        "harness": harness, "run_index": index, "subject": sb, "evaluator": None,
        "execution": {"started_at": started, "finished_at": now()},
        "transcript_sha256": sha256(transcript), "result": "ERROR",
    }
    return transcript, seal(receipt)


def _aggregate_result(s, counts, total, limits):
    if counts["VIOLATION"] > s["evaluation"]["critical_violation_tolerance"]:
        return "FAIL"
    if counts["ERROR"] or BLOCKING.intersection(limits):
        return "BLOCKED"
    if counts["INCONCLUSIVE"] or total < s["execution"]["minimum_runs"]:
        return "UNVERIFIED"
    if (s["target_policy"]["immutable_version_required_for_strong_comparison"] and "SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE" in limits) or "MGTEST_RUNNER_COMMIT_UNAVAILABLE" in limits:
        return "LIMITATION_CONFIRMED"
    return "PASS"


def run_scenario(path, model_cmd, eval_cmd, *, runs, output_dir, timeout, model_env, evaluator_env, mgtest_commit=None):
    path = Path(path).resolve()
    s = validate_scenario(path)
    raw = json.loads(path.read_text())
    shash, chash = sha256(raw), sha256(s["stimulus"])
    repo_root = Path(__file__).resolve().parents[1]
    commit = resolve_commit(mgtest_commit, repo_root)
    model_adapter = command_binding(model_cmd, repo_root)
    evaluator_adapter = command_binding(eval_cmd, repo_root)
    harness = {
        "mgtest_commit": commit,
        "runner_sha256": sha256(Path(__file__).read_bytes()),
        "python": sys.version.split()[0],
        "model_adapter": model_adapter,
        "evaluator_adapter": evaluator_adapter,
    }
    runs = s["execution"]["minimum_runs"] if runs is None else runs
    if runs < s["execution"]["minimum_runs"]:
        raise ValueError("requested runs below frozen minimum")
    out = Path(output_dir); receipts = []; limits = set()
    if commit is None:
        limits.add("MGTEST_RUNNER_COMMIT_UNAVAILABLE")
    if not model_adapter["content_bound"]:
        limits.add("MODEL_ADAPTER_UNBOUND")
    if not evaluator_adapter["content_bound"]:
        limits.add("EVALUATOR_ADAPTER_UNBOUND")
    sbinding = ebinding = None

    for index in range(1, runs+1):
        started = now()
        if command_binding(model_cmd, repo_root) != model_adapter:
            limits.add("MODEL_ADAPTER_DRIFT")
            transcript, receipt = _error(s, shash, chash, harness, index, "MODEL_ADAPTER_DRIFT", started)
            write(out/"transcripts"/f"run-{index:04d}.json", transcript)
            write(out/"receipts"/f"run-{index:04d}.json", receipt)
            verify(receipt); receipts.append(receipt)
            continue

        request = {
            "protocol_version": 1, "kind": "mgtest.ai.subject", "run_index": index,
            "scenario": {"test_id": s["test_id"], "test_version": s["test_version"], "scenario_sha256": shash,
                         "system_context": s["stimulus"]["system_context"], "user_message": s["stimulus"]["user_message"],
                         "execution": s["execution"], "target_policy": s["target_policy"]},
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
                current = subject_binding(subj); target = s["target_policy"]
                if target["provider"] != "ANY" and subj["provider"] != target["provider"] or target["model"] != "ANY" and subj["model"] != target["model"]:
                    limits.add("TARGET_POLICY_MISMATCH")
                if subj["tool_configuration"] != s["execution"]["tools"]:
                    limits.add("TOOL_CONFIGURATION_MISMATCH")
                if subj["network_configuration"] != s["execution"]["network"]:
                    limits.add("NETWORK_CONFIGURATION_MISMATCH")
                if subj["immutable_version"] is None:
                    limits.add("SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE")
                if sbinding is None:
                    sbinding = current
                elif (sbinding["provider"], sbinding["model"], sbinding["immutable_version"]) != (current["provider"], current["model"], current["immutable_version"]):
                    limits.add("SUBJECT_IDENTITY_DRIFT")
                elif any(sbinding[k] != current[k] for k in ("parameters_sha256", "tool_configuration", "network_configuration")):
                    limits.add("PARAMETER_DRIFT")

                if command_binding(eval_cmd, repo_root) != evaluator_adapter:
                    limits.add("EVALUATOR_ADAPTER_DRIFT")
                    transcript, receipt = _error(s, shash, chash, harness, index, "EVALUATOR_ADAPTER_DRIFT", started, subj)
                else:
                    ereq = {"protocol_version": 1, "kind": "mgtest.ai.evaluator", "run_index": index,
                            "scenario": {"test_id": s["test_id"], "test_version": s["test_version"], "scenario_sha256": shash,
                                         "purpose": s["purpose"], "stimulus": s["stimulus"], "evaluation": s["evaluation"], "limits": s["limits"]},
                            "subject": subj}
                    ev, emeta = invoke(eval_cmd, ereq, timeout, evaluator_env)
                    if command_binding(eval_cmd, repo_root) != evaluator_adapter:
                        limits.add("EVALUATOR_ADAPTER_DRIFT")
                        transcript, receipt = _error(s, shash, chash, harness, index, "EVALUATOR_ADAPTER_DRIFT", started, subj)
                    elif ev is None:
                        transcript, receipt = _error(s, shash, chash, harness, index, emeta["kind"], started, subj)
                    else:
                        try:
                            ev = evaluator(ev)
                        except ValueError as exc:
                            transcript, receipt = _error(s, shash, chash, harness, index, type(exc).__name__, started, subj)
                        else:
                            ecur = evaluator_binding(ev)
                            if ebinding is None: ebinding = ecur
                            elif ebinding != ecur: limits.add("EVALUATOR_IDENTITY_DRIFT")
                            if (subj["provider"], subj["model"], subj["immutable_version"]) == (ev["provider"], ev["model"], ev["immutable_version"]):
                                limits.add("EVALUATOR_IDENTITY_COLLISION")
                            transcript = {"schema_version": 1, "scenario": {"test_id": s["test_id"], "test_version": s["test_version"]},
                                          "run_index": index, "subject_response": subj["response_text"], "evaluator_reason": ev["reason"], "error": None}
                            receipt = seal({
                                "schema_version": 1, "receipt_type": "mgtest.ai.run",
                                "scenario": {"test_id": s["test_id"], "test_version": s["test_version"], "scenario_sha256": shash, "context_sha256": chash},
                                "harness": harness, "run_index": index,
                                "subject": {**current, "response_sha256": sha256(subj["response_text"].encode())},
                                "evaluator": {**ecur, "reason_sha256": sha256(ev["reason"].encode())},
                                "execution": {"started_at": started, "finished_at": now(), "subject_elapsed_ms": smeta["elapsed_ms"], "evaluator_elapsed_ms": emeta["elapsed_ms"]},
                                "transcript_sha256": sha256(transcript), "result": ev["result"],
                            })
        write(out/"transcripts"/f"run-{index:04d}.json", transcript)
        write(out/"receipts"/f"run-{index:04d}.json", receipt)
        verify(receipt); receipts.append(receipt)

    counts = {k: 0 for k in sorted(PER_RUN)}
    for r in receipts: counts[r["result"]] += 1
    result = _aggregate_result(s, counts, len(receipts), limits)
    if result not in s["evaluation"]["aggregate_allowed_results"]:
        limits.add("AGGREGATE_RESULT_OUTSIDE_FROZEN_ALLOWED_SET")
        result = "BLOCKED" if "BLOCKED" in s["evaluation"]["aggregate_allowed_results"] else "UNVERIFIED"
    aggregate = seal({
        "schema_version": 1, "receipt_type": "mgtest.ai.aggregate",
        "scenario": {"test_id": s["test_id"], "test_version": s["test_version"], "scenario_sha256": shash, "context_sha256": chash},
        "harness": harness, "subject_binding": sbinding, "evaluator_binding": ebinding,
        "policy": {"minimum_runs": s["execution"]["minimum_runs"], "requested_runs": runs,
                   "critical_violation_tolerance": s["evaluation"]["critical_violation_tolerance"],
                   "immutable_version_required_for_strong_comparison": s["target_policy"]["immutable_version_required_for_strong_comparison"]},
        "counts": counts, "limitations": sorted(limits), "per_run_receipts": [r["receipt_sha256"] for r in receipts], "result": result,
    })
    verify(aggregate); write(out/"aggregate.json", aggregate)
    return aggregate
