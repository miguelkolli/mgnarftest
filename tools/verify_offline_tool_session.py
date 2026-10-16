#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

try:
    from .ai_runner_protocol import sha256, verify
    from .offline_tool_agent import ToolAgentError, parse_action, validate_spec
    from .offline_tool_profile import PROFILE_ID, ToolProfileError, verify_execution
    from .verify_ai_evidence import HEX40, HEX64, load, verify_adapter_binding
except ImportError:
    from ai_runner_protocol import sha256, verify
    from offline_tool_agent import ToolAgentError, parse_action, validate_spec
    from offline_tool_profile import PROFILE_ID, ToolProfileError, verify_execution
    from verify_ai_evidence import HEX40, HEX64, load, verify_adapter_binding


class ToolSessionEvidenceError(ValueError):
    pass


def _exact(value, keys, where):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ToolSessionEvidenceError(f"{where}: fields invalid")


def _subject_identity(action):
    return {
        "provider": action["provider"],
        "model": action["model"],
        "immutable_version": action["immutable_version"],
        "parameters_sha256": sha256(action["parameters"]),
    }


def verify_bundle(spec_path, bundle_dir, expected_mgtest_commit=None):
    bundle = Path(bundle_dir)
    try:
        spec = validate_spec(load(spec_path))
    except (ToolAgentError, ValueError) as exc:
        raise ToolSessionEvidenceError(f"spec invalid: {exc}") from exc
    receipt = load(bundle / "session.json")
    transcript = load(bundle / "transcript.json")
    try:
        verify(receipt)
    except ValueError as exc:
        raise ToolSessionEvidenceError(str(exc)) from exc

    _exact(
        receipt,
        {
            "schema_version",
            "receipt_type",
            "profile",
            "mgtest_commit",
            "runner_sha256",
            "adapter_binding",
            "spec_sha256",
            "subject_binding",
            "transcript_sha256",
            "provider_context_chain_sha256",
            "tool_receipts",
            "final_state_sha256",
            "final_response_sha256",
            "limitations",
            "status",
            "receipt_sha256",
        },
        "session",
    )
    if (
        receipt["schema_version"] != 1
        or receipt["receipt_type"] != "mgtest.ai.offline-tool-session"
    ):
        raise ToolSessionEvidenceError("session type/version invalid")
    if receipt["profile"] != PROFILE_ID or receipt["status"] != "COMPLETED":
        raise ToolSessionEvidenceError("session profile/status invalid")
    commit = receipt["mgtest_commit"]
    if commit is not None and (
        not isinstance(commit, str) or not HEX40.fullmatch(commit)
    ):
        raise ToolSessionEvidenceError("session MGnarfTest commit invalid")
    if expected_mgtest_commit is not None and commit != expected_mgtest_commit:
        raise ToolSessionEvidenceError("session MGnarfTest commit mismatch")
    if (
        not isinstance(receipt["runner_sha256"], str)
        or not HEX64.fullmatch(receipt["runner_sha256"])
    ):
        raise ToolSessionEvidenceError("runner_sha256 invalid")
    if (
        not isinstance(receipt["provider_context_chain_sha256"], str)
        or not HEX64.fullmatch(receipt["provider_context_chain_sha256"])
    ):
        raise ToolSessionEvidenceError("provider context chain hash invalid")
    verify_adapter_binding(receipt["adapter_binding"], "session.adapter_binding")
    if receipt["spec_sha256"] != sha256(spec):
        raise ToolSessionEvidenceError("spec hash mismatch")
    if receipt["transcript_sha256"] != sha256(transcript):
        raise ToolSessionEvidenceError("transcript hash mismatch")

    _exact(
        transcript,
        {"schema_version", "profile", "spec_sha256", "steps"},
        "transcript",
    )
    if (
        transcript["schema_version"] != 1
        or transcript["profile"] != PROFILE_ID
        or transcript["spec_sha256"] != receipt["spec_sha256"]
    ):
        raise ToolSessionEvidenceError("transcript header invalid")
    if not isinstance(transcript["steps"], list) or not transcript["steps"]:
        raise ToolSessionEvidenceError("transcript steps invalid")

    state = json.loads(json.dumps(spec["initial_state"]))
    expected_tool_hashes = []
    provider_context_chain = []
    subject_binding = None
    final_response = None
    final_seen = False
    tool_index = 0

    for expected_step, item in enumerate(transcript["steps"], 1):
        _exact(
            item,
            {"step", "action", "tool_result", "tool_receipt_sha256"},
            f"step[{expected_step}]",
        )
        if item["step"] != expected_step or final_seen:
            raise ToolSessionEvidenceError("transcript step ordering invalid")
        try:
            action = parse_action(item["action"])
        except ToolAgentError as exc:
            raise ToolSessionEvidenceError(f"step action invalid: {exc}") from exc
        identity = _subject_identity(action)
        if subject_binding is None:
            subject_binding = identity
        elif identity != subject_binding:
            raise ToolSessionEvidenceError("subject identity/parameter drift")

        if "provider_context" in action:
            provider_context_chain.append(action["provider_context"])

        if action["action"] == "final":
            if (
                item["tool_result"] is not None
                or item["tool_receipt_sha256"] is not None
            ):
                raise ToolSessionEvidenceError("final step contains tool evidence")
            final_response = action["response_text"]
            final_seen = True
            continue

        if (
            not isinstance(item["tool_receipt_sha256"], str)
            or not HEX64.fullmatch(item["tool_receipt_sha256"])
        ):
            raise ToolSessionEvidenceError("tool receipt hash invalid")
        tool_index += 1
        tool_receipt = load(
            bundle / "tool-receipts" / f"call-{tool_index:04d}.json"
        )
        if tool_receipt.get("receipt_sha256") != item["tool_receipt_sha256"]:
            raise ToolSessionEvidenceError("tool receipt reference mismatch")
        plan = {
            "schema_version": 1,
            "profile": PROFILE_ID,
            "calls": [
                {
                    "call_id": action["call_id"],
                    "tool": action["tool"],
                    "arguments": action["arguments"],
                }
            ],
        }
        try:
            verified = verify_execution(plan, tool_receipt, state)
        except ToolProfileError as exc:
            raise ToolSessionEvidenceError(f"tool receipt invalid: {exc}") from exc
        state = verified["final_state"]
        actual_result = tool_receipt["executions"][0]["result"]
        if item["tool_result"] != actual_result:
            raise ToolSessionEvidenceError(
                "transcript tool result does not match execution receipt"
            )
        expected_tool_hashes.append(tool_receipt["receipt_sha256"])

    if not final_seen or final_response is None:
        raise ToolSessionEvidenceError("session has no final response")
    if receipt["tool_receipts"] != expected_tool_hashes:
        raise ToolSessionEvidenceError("session tool receipt list mismatch")
    if receipt["subject_binding"] != subject_binding:
        raise ToolSessionEvidenceError("session subject binding mismatch")
    if receipt["provider_context_chain_sha256"] != sha256(provider_context_chain):
        raise ToolSessionEvidenceError("provider continuation context chain mismatch")
    if receipt["final_state_sha256"] != sha256(state):
        raise ToolSessionEvidenceError("final state hash mismatch")
    if receipt["final_response_sha256"] != sha256(final_response.encode()):
        raise ToolSessionEvidenceError("final response hash mismatch")
    expected_limits = (
        []
        if subject_binding["immutable_version"] is not None
        else ["SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE"]
    )
    if receipt["limitations"] != expected_limits:
        raise ToolSessionEvidenceError("session limitations mismatch")
    return {
        "status": "VERIFIED",
        "mgtest_commit": commit,
        "tool_calls": len(expected_tool_hashes),
        "subject_binding": subject_binding,
        "limitations": expected_limits,
        "provider_contexts": len(provider_context_chain),
        "provider_context_chain_sha256": receipt[
            "provider_context_chain_sha256"
        ],
        "session_receipt_sha256": receipt["receipt_sha256"],
    }


def main(argv=None):
    p = argparse.ArgumentParser(
        description="Verify an offline MGnarfTest tool-agent evidence bundle."
    )
    p.add_argument("--spec", required=True)
    p.add_argument("--bundle", required=True)
    p.add_argument("--expected-mgtest-commit")
    args = p.parse_args(argv)
    try:
        result = verify_bundle(
            args.spec, args.bundle, args.expected_mgtest_commit
        )
    except ToolSessionEvidenceError as exc:
        print(f"FAIL: {exc}")
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
