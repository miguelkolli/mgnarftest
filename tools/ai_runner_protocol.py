import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

PER_RUN = {"COMPLIANT", "VIOLATION", "INCONCLUSIVE", "ERROR"}
SAFE_ENV = {"PATH", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT", "WINDIR"}
BLOCKING = {
    "EVALUATOR_IDENTITY_COLLISION", "SUBJECT_IDENTITY_DRIFT",
    "EVALUATOR_IDENTITY_DRIFT", "PARAMETER_DRIFT",
    "TARGET_POLICY_MISMATCH", "TOOL_CONFIGURATION_MISMATCH",
    "NETWORK_CONFIGURATION_MISMATCH",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256(value):
    if not isinstance(value, (bytes, bytearray)):
        value = canonical(value)
    return hashlib.sha256(value).hexdigest()


def seal(receipt):
    body = dict(receipt)
    body.pop("receipt_sha256", None)
    receipt["receipt_sha256"] = sha256(body)
    return receipt


def verify(receipt):
    body = dict(receipt)
    actual = body.pop("receipt_sha256", None)
    if actual != sha256(body):
        raise ValueError("receipt hash mismatch")
    return True


def parse_command(raw, flag):
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{flag}: JSON array required") from exc
    if not isinstance(value, list) or not value or not all(isinstance(x, str) and x for x in value):
        raise ValueError(f"{flag}: non-empty JSON array of strings required")
    return value


def resolve_commit(explicit, root):
    value = explicit or os.environ.get("MGTEST_SHA")
    if value is None:
        try:
            value = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                text=True, stderr=subprocess.DEVNULL, timeout=5,
            ).strip()
        except (OSError, subprocess.SubprocessError):
            value = None
    if value is not None:
        value = value.lower()
        if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError("MGnarfTest commit must be exact 40-hex SHA")
    return value


def _env(names):
    env = {k: v for k, v in os.environ.items() if k in SAFE_ENV}
    for name in names:
        if name not in os.environ:
            raise ValueError(f"adapter environment variable unavailable: {name}")
        env[name] = os.environ[name]
    return env


def invoke(command, request, timeout, env_names):
    start = time.monotonic()
    try:
        proc = subprocess.run(
            command, input=json.dumps(request, ensure_ascii=False), text=True,
            capture_output=True, timeout=timeout, env=_env(env_names), check=False,
        )
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        return None, {"kind": type(exc).__name__, "elapsed_ms": int((time.monotonic()-start)*1000)}
    meta = {"elapsed_ms": int((time.monotonic()-start)*1000)}
    if proc.returncode:
        return None, {**meta, "kind": "AdapterExit", "code": proc.returncode}
    try:
        value = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None, {**meta, "kind": "AdapterInvalidJSON"}
    if not isinstance(value, dict):
        return None, {**meta, "kind": "AdapterInvalidShape"}
    return value, meta


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def subject(value):
    keys = {"provider", "model", "immutable_version", "parameters", "tool_configuration", "network_configuration", "response_text"}
    if set(value) != keys:
        raise ValueError("subject response fields invalid")
    if not _text(value["provider"]) or not _text(value["model"]):
        raise ValueError("subject provider/model invalid")
    if value["immutable_version"] is not None and not _text(value["immutable_version"]):
        raise ValueError("subject immutable_version invalid")
    if not isinstance(value["parameters"], dict) or not _text(value["tool_configuration"]):
        raise ValueError("subject parameters/tool configuration invalid")
    if not isinstance(value["network_configuration"], bool) or not isinstance(value["response_text"], str):
        raise ValueError("subject network/response invalid")
    return value


def evaluator(value):
    keys = {"evaluator_id", "evaluator_version", "provider", "model", "immutable_version", "result", "reason"}
    if set(value) != keys:
        raise ValueError("evaluator response fields invalid")
    if not all(_text(value[k]) for k in ("evaluator_id", "evaluator_version", "provider", "model")):
        raise ValueError("evaluator identity invalid")
    if value["immutable_version"] is not None and not _text(value["immutable_version"]):
        raise ValueError("evaluator immutable_version invalid")
    if value["result"] not in PER_RUN - {"ERROR"} or not isinstance(value["reason"], str):
        raise ValueError("evaluator result/reason invalid")
    return value


def subject_binding(value):
    return {
        "provider": value["provider"], "model": value["model"],
        "immutable_version": value["immutable_version"],
        "parameters_sha256": sha256(value["parameters"]),
        "tool_configuration": value["tool_configuration"],
        "network_configuration": value["network_configuration"],
    }


def evaluator_binding(value):
    return {k: value[k] for k in ("evaluator_id", "evaluator_version", "provider", "model", "immutable_version")}
