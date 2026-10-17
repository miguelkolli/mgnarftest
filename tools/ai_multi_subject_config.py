import json
import re
from pathlib import Path

CONFIG_TYPE = "mgtest.ai.multi-subject-config"
LABEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class MultiSubjectConfigError(ValueError):
    pass


def _exact(value, keys, where):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise MultiSubjectConfigError(f"{where}: fields invalid")


def _adapter(value, where):
    _exact(value, {"command", "env_names"}, where)
    command = value["command"]
    if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
        raise MultiSubjectConfigError(f"{where}.command: non-empty string array required")
    env_names = value["env_names"]
    if not isinstance(env_names, list) or len(set(env_names)) != len(env_names):
        raise MultiSubjectConfigError(f"{where}.env_names: unique string array required")
    for name in env_names:
        if not isinstance(name, str) or not ENV_RE.fullmatch(name):
            raise MultiSubjectConfigError(f"{where}.env_names: invalid environment variable name")
    return {"command": list(command), "env_names": list(env_names)}


def validate_config(value):
    _exact(value, {"schema_version", "config_type", "subjects", "evaluator_a", "evaluator_b"}, "config")
    if value["schema_version"] != 1 or value["config_type"] != CONFIG_TYPE:
        raise MultiSubjectConfigError("config type/version invalid")
    subjects = value["subjects"]
    if not isinstance(subjects, list) or len(subjects) < 2:
        raise MultiSubjectConfigError("at least two subjects required")
    clean_subjects = []
    labels = set()
    for index, subject in enumerate(subjects):
        where = f"subjects[{index}]"
        _exact(subject, {"label", "command", "env_names"}, where)
        label = subject["label"]
        if not isinstance(label, str) or not LABEL_RE.fullmatch(label):
            raise MultiSubjectConfigError(f"{where}.label invalid")
        if label in labels:
            raise MultiSubjectConfigError("subject labels must be unique")
        labels.add(label)
        adapter = _adapter({"command": subject["command"], "env_names": subject["env_names"]}, where)
        clean_subjects.append({"label": label, **adapter})
    return {
        "schema_version": 1,
        "config_type": CONFIG_TYPE,
        "subjects": clean_subjects,
        "evaluator_a": _adapter(value["evaluator_a"], "evaluator_a"),
        "evaluator_b": _adapter(value["evaluator_b"], "evaluator_b"),
    }


def load_config(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MultiSubjectConfigError(f"config unreadable: {exc}") from exc
    return validate_config(value)
