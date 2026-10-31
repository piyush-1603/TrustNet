"""Campaign advisories: how projects exchange what they found, with no central server.

A project that detected a coordinated campaign writes an advisory file (accounts, PR ids, evidence).
Any other project can import it. The engine only honors an advisory whose issuer the importing
project already trusts (see trust.evaluate_author), so a fake project cannot get anyone held.
Only handles and evidence are published: no PR text, no personal data beyond the handle.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

FORMAT = "trustnet-advisory/1"


def build_advisory(issuer, campaigns, policy_hash, now=None):
    """Advisory dict for the flagged campaigns in `campaigns`, issued by project `issuer`."""
    now = now or datetime.now(timezone.utc)
    return {
        "format": FORMAT, "issuer": issuer, "issued_at": now.isoformat(), "policy_hash": policy_hash,
        "campaigns": [{"id": c.id, "kind": getattr(c, "kind", "text"), "authors": sorted(c.authors), "pr_ids": list(c.pr_ids),
                       "projects": list(c.projects), "score": round(c.score, 4),
                       "evidence": list(c.evidence), "embedding_used": c.embedding_used}
                      for c in campaigns if c.flagged],
    }


def load_advisory(path):
    """Read and validate an advisory file; raise ValueError naming the file and field."""
    path = Path(path)
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path.name}: cannot read advisory: {exc}") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise ValueError(f"{path.name}: not a {FORMAT} file")
    if not isinstance(data.get("issuer"), str) or not data["issuer"].strip():
        raise ValueError(f"{path.name}: 'issuer' must be a non-empty string")
    campaigns = data.get("campaigns")
    if not isinstance(campaigns, list):
        raise ValueError(f"{path.name}: 'campaigns' must be a list")
    for i, campaign in enumerate(campaigns):
        if (not isinstance(campaign, dict) or not isinstance(campaign.get("id"), str)
                or not isinstance(campaign.get("authors"), list)
                or not all(isinstance(a, str) for a in campaign["authors"])):
            raise ValueError(f"{path.name}: campaigns[{i}] needs a string 'id' and a list of string 'authors'")
    return data
