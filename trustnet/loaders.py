"""Read a network folder and the policy file, checking input at the trust boundary.

Layout (see docs/PLAN.md): <dir>/projects/<id>.json, <dir>/accounts.json, <dir>/prs.json.
labels.json (simulator ground truth) is never read here.
"""

import hashlib
import json
from pathlib import Path

from .models import Account, Denounce, Network, PR, Project, Trust, Vouch, parse_time

POLICY_PATH = Path(__file__).resolve().parent.parent / "policy.json"

# section -> key -> (min, max, integer?); min is exclusive for "decay" and "vouch_weight" via MIN_EXCLUSIVE.
_RULES = {
    "trust": {"decay": (0, 1, False), "max_hops": (1, 10, True), "min_trust": (0, 1, False),
              "vouch_weight": (0, 1, False), "top_k": (1, 100, True), "no_evidence_factor": (0, 1, False)},
    "decision": {"hold_threshold": (0, 1, False), "accept_threshold": (0, 1, False)},
    "campaigns": {"similarity_threshold": (0, 1, False), "min_prs": (1, 10**6, True),
                  "min_projects": (1, 10**6, True), "window_hours": (0, 10**4, False),
                  "min_young_share": (0, 1, False), "young_days": (0, 10**4, False),
                  "flag_threshold": (0, 1, False), "size_scale": (1, 10**6, False),
                  "projects_scale": (1, 10**6, False), "size_weight": (0, 1, False),
                  "projects_weight": (0, 1, False), "young_weight": (0, 1, False)},
}
_MIN_EXCLUSIVE = {"decay", "vouch_weight"}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def load_policy(path=None):
    """Return (policy dict, 12-hex hash of its canonical JSON). The hash goes in every output."""
    path = Path(path) if path else POLICY_PATH
    try:
        policy = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: cannot read policy: {exc}") from exc
    for section, keys in _RULES.items():
        block = policy.get(section)
        if not isinstance(block, dict):
            raise ValueError(f"{path}: missing section '{section}'")
        for key, (low, high, integer) in keys.items():
            value = block.get(key)
            if not _number(value) or (integer and int(value) != value):
                raise ValueError(f"{path}: {section}.{key} must be a {'whole ' if integer else ''}number")
            below = value <= low if key in _MIN_EXCLUSIVE else value < low
            if below or value > high:
                raise ValueError(f"{path}: {section}.{key}={value} is out of range")
    canonical = json.dumps(policy, sort_keys=True, separators=(",", ":"))
    return policy, hashlib.sha256(canonical.encode()).hexdigest()[:12]


def _read(path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path.name}: cannot read: {exc}") from exc


def _rows(data, where):
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise ValueError(f"{where}: must be a list of objects")
    return data


def _text(row, key, where):
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}: '{key}' must be a non-empty string")
    return value


def _optional(row, key, where):
    value = row.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{where}: '{key}' must be a string or null")
    return value or None


def _time(row, key, where, required=False):
    value = row.get(key)
    if value is None:
        if required:
            raise ValueError(f"{where}: '{key}' is required")
        return None
    try:
        parse_time(value)
    except ValueError as exc:
        raise ValueError(f"{where}: '{key}': {exc}") from exc
    return value


def _project(path):
    data = _read(path)
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: must be an object")
    pid = _text(data, "id", path.name)
    if pid != path.stem:
        raise ValueError(f"{path.name}: id '{pid}' must match the file name")
    trusts, vouches, denounces = [], [], []
    for i, row in enumerate(_rows(data.get("trusts", []), f"{path.name}: trusts")):
        where = f"{path.name}: trusts[{i}]"
        weight = row.get("weight")
        if not _number(weight) or not 0 <= weight <= 1:
            raise ValueError(f"{where}: 'weight' must be a number from 0 to 1")
        trusts.append(Trust(project=_text(row, "project", where), weight=weight))
    for i, row in enumerate(_rows(data.get("vouches", []), f"{path.name}: vouches")):
        where = f"{path.name}: vouches[{i}]"
        vouches.append(Vouch(handle=_text(row, "handle", where), date=_time(row, "date", where),
                             evidence_url=_optional(row, "evidence_url", where)))
    for i, row in enumerate(_rows(data.get("denounces", []), f"{path.name}: denounces")):
        where = f"{path.name}: denounces[{i}]"
        denounces.append(Denounce(handle=_text(row, "handle", where), reason_code=_text(row, "reason_code", where),
                                  evidence_url=_optional(row, "evidence_url", where),
                                  date=_time(row, "date", where), expires=_time(row, "expires", where)))
    return Project(id=pid, name=data.get("name") or pid, trusts=trusts, vouches=vouches, denounces=denounces)


def load_network(path):
    """Load and validate a network folder; raise ValueError naming the file and field on bad input."""
    root = Path(path)
    files = sorted((root / "projects").glob("*.json"))
    if not files:
        raise ValueError(f"{root}: no projects/*.json files found")
    projects = {p.id: p for p in map(_project, files)}
    accounts = {}
    for i, row in enumerate(_rows(_read(root / "accounts.json"), "accounts.json")):
        where = f"accounts.json[{i}]"
        handle = _text(row, "handle", where)
        if handle in accounts:
            raise ValueError(f"{where}: duplicate handle '{handle}'")
        accounts[handle] = Account(handle=handle, created_at=_time(row, "created_at", where, required=True))
    prs, seen = [], set()
    for i, row in enumerate(_rows(_read(root / "prs.json"), "prs.json")):
        where = f"prs.json[{i}]"
        pr_id = _text(row, "id", where)
        if pr_id in seen:
            raise ValueError(f"{where}: duplicate PR id '{pr_id}'")
        seen.add(pr_id)
        prs.append(PR(id=pr_id, project=_text(row, "project", where), author=_text(row, "author", where),
                      created_at=_time(row, "created_at", where, required=True),
                      title=row.get("title") or "", body=row.get("body") or "", diff_text=row.get("diff_text") or ""))
    return Network(projects=projects, accounts=accounts, prs=prs)
