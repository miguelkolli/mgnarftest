#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

try:
    from .ai_runner_protocol import evaluator, evaluator_binding, seal, verify, sha256
except ImportError:
    from ai_runner_protocol import evaluator, evaluator_binding, seal, verify, sha256

HEX64 = re.compile(r"^[0-9a-f]{64}$")
EVALUATOR_RESULTS = {"COMPLIANT", "VIOLATION", "INCONCLUSIVE"}


class ConsensusError(ValueError):
    pass


def _subject_identity(value):
    if not isinstance(value, dict):
        raise ConsensusError("subject binding must be object")
    for key in ("provider", "model"):
        if not isinstance(value.get(key), str) or not value[key].strip():
            raise ConsensusError(f"subject.{key} invalid")
    immutable = value.get("immutable_version")
    if immutable is not None and (not isinstance(immutable, str) or not immutable.strip()):
        raise ConsensusError("subject.immutable_version invalid")
    return {"provider": value["provider"], "model": value["model"], "immutable_version": immutable}


def _eval_record(value):
    parsed = evaluator(dict(value))
    binding = evaluator_binding(parsed)
    return {"binding": binding, "result": parsed["result"], "reason_sha256": sha256(parsed["reason"].encode())}


def _model_identity(value):
    return (value["provider"], value["model"], value["immutable_version"])


def _blockers(subject, a_binding, b_binding):
    blockers = []
    if _model_identity(a_binding) == _model_identity(b_binding):
        blockers.append("EVALUATOR_PAIR_IDENTITY_COLLISION")
    if _model_identity(subject) == _model_identity(a_binding):
        blockers.append("EVALUATOR_A_SUBJECT_IDENTITY_COLLISION")
    if _model_identity(subject) == _model_identity(b_binding):
        blockers.append("EVALUATOR_B_SUBJECT_IDENTITY_COLLISION")
    return sorted(set(blockers))


def _decision(a_result, b_result, blockers):
    if blockers:
        return "BLOCKED", "ERROR"
    if "VIOLATION" in {a_result, b_result}:
        status = "AGREED" if a_result == b_result == "VIOLATION" else "CONSERVATIVE_VIOLATION"
        return status, "VIOLATION"
    if a_result == b_result == "COMPLIANT":
        return "AGREED", "COMPLIANT"
    if a_result == b_result == "INCONCLUSIVE":
        return "AGREED", "INCONCLUSIVE"
    return "DISAGREEMENT", "INCONCLUSIVE"


def build_consensus_record(subject_binding, evaluator_a, evaluator_b):
    subject = _subject_identity(subject_binding)
    a = _eval_record(evaluator_a)
    b = _eval_record(evaluator_b)
    blockers = _blockers(subject, a["binding"], b["binding"])
    status, result = _decision(a["result"], b["result"], blockers)
    return {
        "subject_identity": subject,
        "evaluator_a": a,
        "evaluator_b": b,
        "consensus": {"status": status, "result": result, "blockers": blockers},
    }


def build_consensus_receipt(source_run_receipt_sha256, subject_binding, evaluator_a, evaluator_b):
    if not isinstance(source_run_receipt_sha256, str) or not HEX64.fullmatch(source_run_receipt_sha256):
        raise ConsensusError("source run receipt hash invalid")
    record = build_consensus_record(subject_binding, evaluator_a, evaluator_b)
    return seal({
        "schema_version": 1,
        "receipt_type": "mgtest.ai.evaluator-consensus",
        "source_run_receipt_sha256": source_run_receipt_sha256,
        **record,
    })


def _require_exact(value, keys, where):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ConsensusError(f"{where}: fields invalid")


def _verify_binding(value, where):
    keys = {"evaluator_id", "evaluator_version", "provider", "model", "immutable_version"}
    _require_exact(value, keys, where)
    for key in ("evaluator_id", "evaluator_version", "provider", "model"):
        if not isinstance(value[key], str) or not value[key].strip():
            raise ConsensusError(f"{where}.{key} invalid")
    immutable = value["immutable_version"]
    if immutable is not None and (not isinstance(immutable, str) or not immutable.strip()):
        raise ConsensusError(f"{where}.immutable_version invalid")


def _verify_eval_record(value, where):
    _require_exact(value, {"binding", "result", "reason_sha256"}, where)
    _verify_binding(value["binding"], f"{where}.binding")
    if value["result"] not in EVALUATOR_RESULTS:
        raise ConsensusError(f"{where}.result invalid")
    if not isinstance(value["reason_sha256"], str) or not HEX64.fullmatch(value["reason_sha256"]):
        raise ConsensusError(f"{where}.reason_sha256 invalid")


def verify_consensus_record(record):
    _require_exact(record, {"subject_identity", "evaluator_a", "evaluator_b", "consensus"}, "record")
    subject = _subject_identity(record["subject_identity"])
    _verify_eval_record(record["evaluator_a"], "evaluator_a")
    _verify_eval_record(record["evaluator_b"], "evaluator_b")
    blockers = _blockers(subject, record["evaluator_a"]["binding"], record["evaluator_b"]["binding"])
    status, result = _decision(record["evaluator_a"]["result"], record["evaluator_b"]["result"], blockers)
    _require_exact(record["consensus"], {"status", "result", "blockers"}, "consensus")
    if record["consensus"] != {"status": status, "result": result, "blockers": blockers}:
        raise ConsensusError("consensus decision mismatch")
    return True


def verify_consensus_receipt(receipt):
    try:
        verify(receipt)
    except ValueError as exc:
        raise ConsensusError(str(exc)) from exc
    _require_exact(
        receipt,
        {"schema_version", "receipt_type", "source_run_receipt_sha256", "subject_identity", "evaluator_a", "evaluator_b", "consensus", "receipt_sha256"},
        "receipt",
    )
    if receipt["schema_version"] != 1 or receipt["receipt_type"] != "mgtest.ai.evaluator-consensus":
        raise ConsensusError("receipt type/version invalid")
    if not isinstance(receipt["source_run_receipt_sha256"], str) or not HEX64.fullmatch(receipt["source_run_receipt_sha256"]):
        raise ConsensusError("source run receipt hash invalid")
    verify_consensus_record({k: receipt[k] for k in ("subject_identity", "evaluator_a", "evaluator_b", "consensus")})
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a fail-closed two-evaluator consensus receipt.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        _require_exact(payload, {"source_run_receipt_sha256", "subject_binding", "evaluator_a", "evaluator_b"}, "input")
        receipt = build_consensus_receipt(
            payload["source_run_receipt_sha256"], payload["subject_binding"], payload["evaluator_a"], payload["evaluator_b"]
        )
        verify_consensus_receipt(receipt)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"BLOCKED: {exc}")
        return 1
    text = json.dumps(receipt, sort_keys=True, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
