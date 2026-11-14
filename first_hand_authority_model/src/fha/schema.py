"""Feature and label schemas, record validation and information status."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = PROJECT_ROOT / "schemas"

UNKNOWN = "UNKNOWN"
NOT_COMPUTED = "NOT_COMPUTED"
SENTINELS = (UNKNOWN, NOT_COMPUTED)

# Information status of a pair. Only SUFFICIENT and LIMITED pairs are scored.
SUFFICIENT = "SUFFICIENT"
LIMITED = "LIMITED"
INSUFFICIENT = "INSUFFICIENT"
INELIGIBLE = "INELIGIBLE"

_TOKEN = re.compile(r"^[A-Z0-9_]+$")


class ValidationError(ValueError):
    """Raised when a record does not match the schema."""


def _load(name: str) -> dict:
    with open(SCHEMA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def file_sha256(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class FeatureSchema:
    raw: dict = field(default_factory=lambda: _load("feature_schema.json"))

    @property
    def version(self) -> str:
        return self.raw["schema_version"]

    @property
    def features(self) -> dict:
        return self.raw["features"]

    @property
    def names(self) -> list[str]:
        return list(self.features)

    @property
    def relation_features(self) -> list[str]:
        return self.raw["relation_features"]

    @property
    def interactions(self) -> list[tuple[str, str]]:
        return [tuple(p) for p in self.raw["derived_interactions"]]

    @property
    def prohibited(self) -> set[str]:
        return set(self.raw["prohibited_keys"])

    def group_of(self, name: str) -> str:
        return self.features[name]["group"]

    def names_in(self, *groups: str) -> list[str]:
        return [n for n in self.names if self.group_of(n) in groups]

    def sha256(self) -> str:
        return file_sha256(SCHEMA_DIR / "feature_schema.json")


@dataclass
class LabelSchema:
    raw: dict = field(default_factory=lambda: _load("label_schema.json"))

    def sha256(self) -> str:
        return file_sha256(SCHEMA_DIR / "label_schema.json")


def _check_value(name: str, value, levels, warnings: list[str]) -> None:
    if not isinstance(value, str):
        raise ValidationError(f"feature '{name}' must be a string, got {type(value).__name__}")
    if value in SENTINELS:
        return
    if levels is None:
        if not _TOKEN.match(value):
            raise ValidationError(f"feature '{name}' value '{value}' is not an UPPER_SNAKE_CASE token")
        warnings.append(f"feature '{name}' has no frozen level list; accepted '{value}' provisionally")
        return
    if value not in levels:
        raise ValidationError(
            f"feature '{name}' value '{value}' is not an allowed level; allowed: {levels + list(SENTINELS)}"
        )


def validate_record(record: dict, schema: FeatureSchema, require_label: bool = False,
                    label_schema: LabelSchema | None = None) -> list[str]:
    """Validate one pair record. Returns warnings; raises ValidationError on errors.

    Missing features are an error: absence must be written explicitly as
    UNKNOWN or NOT_COMPUTED so no value is ever silently filled in.
    """
    warnings: list[str] = []
    if not isinstance(record, dict):
        raise ValidationError("record must be a JSON object")
    for key in ("pair_id", "claim_id", "publisher_id"):
        if not isinstance(record.get(key), str) or not record.get(key):
            raise ValidationError(f"'{key}' must be a non-empty string")
    pid = record["pair_id"]

    bad = schema.prohibited & set(record)
    feats = record.get("features")
    if not isinstance(feats, dict):
        raise ValidationError(f"{pid}: 'features' must be an object")
    bad |= schema.prohibited & set(feats)
    if bad:
        raise ValidationError(f"{pid}: prohibited input field(s) present: {sorted(bad)}")

    expected = set(schema.names) | set(schema.raw["eligibility"])
    missing = expected - set(feats)
    if missing:
        raise ValidationError(f"{pid}: missing feature(s) {sorted(missing)}; use UNKNOWN or NOT_COMPUTED explicitly")
    extra = set(feats) - expected
    if extra:
        raise ValidationError(f"{pid}: unknown feature(s) {sorted(extra)}")

    for name, spec in schema.features.items():
        _check_value(name, feats[name], spec["levels"], warnings)
    for name, spec in schema.raw["eligibility"].items():
        _check_value(name, feats[name], spec["levels"], warnings)

    if "publisher_resolved" in record and not isinstance(record["publisher_resolved"], bool):
        raise ValidationError(f"{pid}: 'publisher_resolved' must be a boolean")
    if "is_synthetic" in record and not isinstance(record["is_synthetic"], bool):
        raise ValidationError(f"{pid}: 'is_synthetic' must be a boolean")

    if require_label:
        if "label" not in record:
            raise ValidationError(f"{pid}: training/evaluation records need a 'label'")
        validate_label(record["label"], label_schema or LabelSchema(), pid)
    return warnings


def validate_label(label: dict, ls: LabelSchema, pid: str = "?") -> None:
    if not isinstance(label, dict):
        raise ValidationError(f"{pid}: 'label' must be an object")
    final = label.get("final")
    if final not in ls.raw["final"]:
        raise ValidationError(f"{pid}: label.final '{final}' not in {ls.raw['final']}")
    if final == "FIRST_HAND_AUTHORITY" and label.get("basis") not in ls.raw["basis"]:
        raise ValidationError(f"{pid}: FIRST_HAND_AUTHORITY needs a basis in {ls.raw['basis']}")
    if final == "NOT_FIRST_HAND_AUTHORITY" and label.get("not_fha_reason") not in ls.raw["not_fha_reason"]:
        raise ValidationError(f"{pid}: NOT_FIRST_HAND_AUTHORITY needs a not_fha_reason")
    if final == "CANNOT_JUDGE" and label.get("cannot_judge_reason") not in ls.raw["cannot_judge_reason"]:
        raise ValidationError(f"{pid}: CANNOT_JUDGE needs a cannot_judge_reason")
    for flag in label.get("flags", []) or []:
        if flag not in ls.raw["flags"]:
            raise ValidationError(f"{pid}: unknown label flag '{flag}'")


def is_missing(value: str) -> bool:
    return value in SENTINELS


def info_status(record: dict, schema: FeatureSchema) -> tuple[str, list[str]]:
    """Return (status, reasons) for a validated record.

    INELIGIBLE   publisher did not exist in its role at the claim date.
    INSUFFICIENT publisher unresolved or its type unknown: not scored.
    LIMITED      type known but every relation feature missing: score is
                 effectively a publisher-type prior and is flagged.
    SUFFICIENT   otherwise.
    These rules are the design's proposal and await mentor approval.
    """
    f = record["features"]
    reasons: list[str] = []
    if f["active_at_claim_date"] == "NO":
        return INELIGIBLE, ["publisher not active in its role at the claim date"]
    if record.get("publisher_resolved") is False:
        return INSUFFICIENT, ["publisher entity could not be resolved"]
    if is_missing(f["publisher_type"]):
        return INSUFFICIENT, [f"publisher_type is {f['publisher_type']}"]
    missing_rel = [n for n in schema.relation_features if is_missing(f[n])]
    if len(missing_rel) == len(schema.relation_features):
        return LIMITED, ["all relation features missing; score reflects publisher type only"]
    if missing_rel:
        reasons.append(f"missing relation features: {missing_rel}")
    return SUFFICIENT, reasons


def unavailable_features(record: dict) -> list[str]:
    return sorted(k for k, v in record["features"].items() if v == NOT_COMPUTED)


def read_jsonl(path: Path | str) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValidationError(f"{path}:{i}: invalid JSON ({e.msg})") from e
    return out


def write_jsonl(path: Path | str, records: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, sort_keys=True) + "\n")
