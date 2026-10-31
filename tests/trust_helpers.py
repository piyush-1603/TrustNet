"""Tiny builders so each trust test shows its whole network in a few lines."""

from datetime import datetime, timezone

from trustnet.models import Denounce, Network, Project, Trust, Vouch

NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
EVIDENCE = "https://example.test/evidence"


def project(pid, trusts=None, vouches=(), denounces=()):
    """trusts: {project_id: weight}; vouches: handles; denounces: Denounce objects from denounce()."""
    return Project(id=pid, name=pid, trusts=[Trust(p, w) for p, w in (trusts or {}).items()],
                   vouches=[Vouch(h, "2026-09-01T00:00:00Z", EVIDENCE) for h in vouches],
                   denounces=list(denounces))


def denounce(handle, evidence=EVIDENCE, expires=None):
    return Denounce(handle=handle, reason_code="spam", evidence_url=evidence, date="2026-10-01T00:00:00Z",
                    expires=expires)


def network(*projects):
    return Network(projects={p.id: p for p in projects})
