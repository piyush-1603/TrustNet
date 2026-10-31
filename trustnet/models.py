"""Plain data classes shared by every TrustNet module (the contract in docs/PLAN.md)."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


def parse_time(value):
    """Return an aware UTC datetime from a datetime or an ISO-8601 string.

    Timestamps are stored exactly as given (string or datetime) and parsed on use.
    A trailing 'Z' is accepted; a naive value is taken to be UTC.
    """
    if not isinstance(value, datetime):
        if not isinstance(value, str):
            raise ValueError(f"not a timestamp: {value!r}")
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"not an ISO-8601 timestamp: {value!r}") from exc
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass
class Trust:
    """A project's trust in another project: weight 0..1."""
    project: str
    weight: float


@dataclass
class Vouch:
    handle: str
    date: str
    evidence_url: str = None


@dataclass
class Denounce:
    handle: str
    reason_code: str
    evidence_url: str = None
    date: str = None
    expires: str = None


@dataclass
class Project:
    id: str
    name: str
    trusts: list = field(default_factory=list)
    vouches: list = field(default_factory=list)
    denounces: list = field(default_factory=list)


@dataclass
class Account:
    handle: str
    created_at: str


@dataclass
class PR:
    id: str
    project: str
    author: str
    created_at: str
    title: str
    body: str
    diff_text: str


@dataclass
class Network:
    projects: dict = field(default_factory=dict)
    accounts: dict = field(default_factory=dict)
    prs: list = field(default_factory=list)


@dataclass
class Decision:
    """What one project (the viewer) should do with one author."""
    pr_id: str
    viewer: str
    author: str
    decision: str  # "ACCEPT" | "PROVISIONAL" | "HOLD"
    belief: float
    disbelief: float
    uncertainty: float
    reasons: list = field(default_factory=list)
    paths: list = field(default_factory=list)
    ignored: list = field(default_factory=list)
    in_campaign: bool = False
    next_steps: list = field(default_factory=list)  # what would move a PROVISIONAL author to ACCEPT


@dataclass
class Campaign:
    id: str
    pr_ids: list
    projects: list
    authors: list
    score: float
    flagged: bool
    evidence: list
    embedding_used: bool
