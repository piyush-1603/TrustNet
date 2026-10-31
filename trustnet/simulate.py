"""
trustnet/simulate.py
====================
Seeded synthetic network generator.  Same seed -> identical JSON files every run.

Public API (do not rename -- contract in docs/PLAN.md):
    generate(n_projects=30, seed=42) -> tuple[Network, dict]
    write_network(net, labels, out_dir) -> None

The second return value of generate() is the labels dict (ground truth).
write_network() expects both so the CLI can call them independently.

Planted scenarios in the default network:
  (a) Spam campaign  -- ~38 reworded PRs, ~20 new accounts, ~25 projects, 2 h window
  (b) Legit bulk dep bump -- 1 old vouched maintainer, same PR to 10 projects (must NOT be flagged)
  (c) Brigade        -- 5 fake projects denounce 1 honest author (T < 0.25 -> ignored)
  (d) Sybil clique   -- fake projects vouch for a spammer (no real trust path -> gains nothing)
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from trustnet.models import Project, Trust, Vouch, Denounce, Account, PR, Network


# ---------------------------------------------------------------------------
# Static name pools (all fictional -- no real people or repos)
# ---------------------------------------------------------------------------
_ADJ = [
    "swift", "open", "bright", "meta", "nano", "hyper", "core", "data",
    "cloud", "edge", "safe", "fast", "pure", "sync", "flux", "grid",
    "node", "base", "auto", "net", "link", "flow", "arch", "deep",
    "light", "smart", "pixel", "byte", "proto", "forge",
]
_NOUN = [
    "kit", "hub", "lab", "ops", "lib", "api", "cli", "app",
    "ware", "net", "box", "flow", "core", "base", "suite",
    "forge", "stack", "tool", "craft", "link",
]
_FIRST = [
    "alice", "bob", "carol", "dave", "eve", "frank", "grace", "hank",
    "iris", "jack", "kate", "leo", "mia", "nate", "opal", "paul",
    "quinn", "rose", "sam", "tara", "uma", "victor", "wendy", "xander",
    "yara", "zach", "aria", "blake", "corey", "dana",
]
_INITIALS = list("abcdefghjkmnpqrstvwxyz")
_PR_VERBS = ["fix", "add", "refactor", "improve", "update", "remove", "document"]
_PR_OBJS = [
    "logging", "tests", "README", "config", "CI", "docs", "types",
    "lint", "error-handling", "deps", "auth", "cache", "api",
]

# ---------------------------------------------------------------------------
# Spam campaign text (variants share >80% tokens -> TF-IDF cosine >= 0.85)
# ---------------------------------------------------------------------------
_SPAM_BASE = (
    "This pull request adds comprehensive error handling to the request module. "
    "The change improves reliability by catching network timeout exceptions and "
    "logging them with structured output. Tests for all edge cases are included. "
    "Please review and merge at your earliest convenience."
)
_SPAM_SWAPS = [
    ("adds comprehensive error handling", "introduces robust exception handling"),
    ("request module", "networking module"),
    ("improves reliability", "enhances stability"),
    ("catching network timeout exceptions", "intercepting connection timeout errors"),
    ("logging them with structured output", "recording them with formatted output"),
    ("Tests for all edge cases are included", "Unit tests covering edge cases are provided"),
    ("Please review and merge at your earliest convenience", "Kindly review and merge when possible"),
]
_SPAM_FILLERS = [
    "Tested on Ubuntu 22.04.",
    "Tested on macOS 14.",
    "Part of the reliability initiative.",
    "Addresses reported flakiness.",
    "Resolves intermittent failures.",
    "Improves test suite coverage.",
]

# ---------------------------------------------------------------------------
# Legit bulk-bump text (identical across all 10 PRs; old account saves it)
# ---------------------------------------------------------------------------
_BUMP_TITLE = "chore: bump requests from 2.28.0 to 2.31.0"
_BUMP_BODY = (
    "Bumps `requests` from 2.28.0 to 2.31.0.\n\n"
    "Changelog:\n"
    "- 2.31.0: Security fix for CVE-2023-32681 (redirect header leak)\n"
    "- 2.30.0: Drop Python 3.7 support\n"
    "- 2.29.0: Add IDNA 3.x support\n\n"
    "Signed-off-by: dependabot[bot] <support@example.com>"
)
_BUMP_DIFF = (
    "--- a/requirements.txt\n+++ b/requirements.txt\n"
    "@@ -1 +1 @@\n-requests==2.28.0\n+requests==2.31.0\n"
)

# Fixed "now" so dates never drift between runs
_NOW = datetime(2026, 10, 31, 20, 0, 0, tzinfo=timezone.utc)


def _iso(dt: datetime) -> str:
    """Serialise a datetime to ISO-8601 UTC (the format the loader expects)."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _spam_variant(rng: random.Random, index: int) -> str:
    """
    Return a reworded spam body that is still >= 0.85 TF-IDF cosine similar
    to the base template.  Applies exactly 2 swaps + a short unique filler.
    """
    text = _SPAM_BASE
    i = index % len(_SPAM_SWAPS)
    j = (i + 1) % len(_SPAM_SWAPS)
    for old, new in (_SPAM_SWAPS[i], _SPAM_SWAPS[j]):
        text = text.replace(old, new)
    text += " " + _SPAM_FILLERS[index % len(_SPAM_FILLERS)]
    return text


def generate(n_projects: int = 30, seed: int = 42):
    """
    Build a synthetic TrustNet network.

    Parameters
    ----------
    n_projects : int
        Number of honest projects (default 30).
    seed : int
        RNG seed. Same seed -> byte-identical JSON output.

    Returns
    -------
    (Network, labels_dict)
        labels_dict keys: campaign_pr_ids, newcomer_handles, attack_handles,
        brigaded_handle, legit_bump_pr_ids, sybil_spammer_handle.
        The trust engine never reads labels; only tests and the CLI use them.
    """
    if n_projects < 1:
        raise ValueError(f"n_projects must be at least 1, got {n_projects}")

    rng = random.Random(seed)  # single seeded RNG; NEVER call random.seed()
    now = _NOW

    # ------------------------------------------------------------------ #
    # 1. Projects                                                         #
    # ------------------------------------------------------------------ #
    proj_ids = [f"proj-{i:02d}" for i in range(1, n_projects + 1)]

    adj_pool = _ADJ[:]
    noun_pool = _NOUN[:]
    rng.shuffle(adj_pool)
    rng.shuffle(noun_pool)

    projects = {}
    for i, pid in enumerate(proj_ids):
        name = f"{adj_pool[i % len(adj_pool)]}-{noun_pool[i % len(noun_pool)]}"
        projects[pid] = Project(id=pid, name=name)

    # Sparse trust graph: 2-4 outgoing edges per project, weight 0.3-1.0
    for pid in proj_ids:
        n_trust = rng.randint(2, 4)
        candidates = [p for p in proj_ids if p != pid]
        rng.shuffle(candidates)
        for target in candidates[:n_trust]:
            w = round(rng.uniform(0.3, 1.0), 2)
            projects[pid].trusts.append(Trust(project=target, weight=w))

    # ------------------------------------------------------------------ #
    # 2. Accounts -- honest (1-7 years old)                              #
    # ------------------------------------------------------------------ #
    accounts = {}
    honest_handles = []

    fn_pool = _FIRST[:]
    rng.shuffle(fn_pool)

    for i in range(200):
        fn = fn_pool[i % len(fn_pool)]
        li = _INITIALS[i % len(_INITIALS)]
        handle = f"{fn}-{li}{i:03d}"
        age_days = rng.randint(365, 365 * 7)
        accounts[handle] = Account(handle=handle,
                                   created_at=now - timedelta(days=age_days))
        honest_handles.append(handle)

    # 15 newcomers: 15-30 days old (> 14 days so NOT auto-flagged as bots)
    newcomer_handles = []
    for i in range(15):
        handle = f"newcomer-{i:02d}"
        age_days = rng.randint(15, 30)
        accounts[handle] = Account(handle=handle,
                                   created_at=now - timedelta(days=age_days))
        newcomer_handles.append(handle)

    # ------------------------------------------------------------------ #
    # 3. Vouches for honest accounts (denser: 20-35 per project)          #
    # ------------------------------------------------------------------ #
    for pid in proj_ids:
        n_vouch = rng.randint(20, 35)
        for handle in rng.sample(honest_handles, min(n_vouch, len(honest_handles))):
            age_days = rng.randint(30, 600)
            projects[pid].vouches.append(Vouch(
                handle=handle,
                date=_iso(now - timedelta(days=age_days)),
                evidence_url=f"https://example.com/vouch/{pid}/{handle}",
            ))

    # ------------------------------------------------------------------ #
    # 4. Normal PRs (~150 varied)                                         #
    # ------------------------------------------------------------------ #
    prs = []
    pr1_author = honest_handles[1]
    if not any(v.handle == pr1_author for v in projects[proj_ids[0]].vouches):
        projects[proj_ids[0]].vouches.append(Vouch(
            handle=pr1_author,
            date=_iso(now - timedelta(days=90)),
            evidence_url=f"https://example.com/vouch/{proj_ids[0]}/{pr1_author}",
        ))

    pr_counter = 1
    for i in range(150):
        if i == 0:
            pid = proj_ids[0]
            author = pr1_author
        elif i == 1:
            pid = proj_ids[0]
            author = honest_handles[0]  # brigaded_handle
        else:
            pid = rng.choice(proj_ids)
            author = rng.choice(honest_handles)
        created = now - timedelta(hours=rng.randint(1, 720))
        verb = rng.choice(_PR_VERBS)
        obj = rng.choice(_PR_OBJS)
        prs.append(PR(
            id=f"pr-{pr_counter:03d}",
            project=pid,
            author=author,
            created_at=created,
            title=f"{verb}: {obj} in {pid}",
            body=(
                f"This PR {verb}s {obj} for {pid}. "
                "Motivation: improve code quality and maintainability. "
                "Changes are backwards compatible and include unit tests."
            ),
            diff_text=(
                f"--- a/src/{obj.replace('-', '_')}.py\n"
                f"+++ b/src/{obj.replace('-', '_')}.py\n"
                "@@ -10,3 +10,5 @@\n"
                "     pass\n"
                f"+    # {verb} {obj}\n"
            ),
        ))
        pr_counter += 1

    # ------------------------------------------------------------------ #
    # 5. PLANTED (a): Spam campaign                                       #
    #    38 reworded PRs * 20 new accounts * 25 projects * 2-hour window  #
    # ------------------------------------------------------------------ #
    spam_handles = []
    for i in range(20):
        handle = f"bot-{i:02d}"
        age_days = rng.randint(1, 13)  # < 14 days -> counted as bot account
        accounts[handle] = Account(handle=handle,
                                   created_at=now - timedelta(days=age_days))
        spam_handles.append(handle)

    spam_projects = rng.sample(proj_ids, min(25, n_projects))
    campaign_pr_ids = []
    campaign_start = now - timedelta(hours=2)
    _spam_titles = [
        "Add error handling to request module",
        "Improve exception handling in networking",
        "Fix timeout handling in requests",
        "Add robust error handling",
        "Enhance error management in requests",
    ]

    for i in range(38):
        pr_id = f"pr-{pr_counter:03d}"
        pr_counter += 1
        pid = spam_projects[i % len(spam_projects)]
        author = spam_handles[i % len(spam_handles)]
        offset = int((i / 38) * 7200)  # spread evenly across 2-hour window
        created = campaign_start + timedelta(seconds=offset)
        campaign_pr_ids.append(pr_id)
        prs.append(PR(
            id=pr_id,
            project=pid,
            author=author,
            created_at=created,
            title=_spam_titles[i % len(_spam_titles)],
            body=_spam_variant(rng, i),
            diff_text=(
                "--- a/src/requests.py\n+++ b/src/requests.py\n"
                "@@ -5,2 +5,4 @@\n try:\n     response = session.get(url)\n"
                "+except Timeout:\n+    logger.error('timeout', exc_info=True)\n"
            ),
        ))

    # ------------------------------------------------------------------ #
    # 6. PLANTED (b): Legitimate bulk dependency bump                     #
    #    Old account (4 yrs) + vouched -> young_share=0 -> score<0.6     #
    # ------------------------------------------------------------------ #
    legit_handle = "maintainer-dep"
    accounts[legit_handle] = Account(
        handle=legit_handle,
        created_at=now - timedelta(days=365 * 4),  # 4-year-old account
    )
    projects[proj_ids[0]].vouches.append(Vouch(
        handle=legit_handle,
        date=_iso(now - timedelta(days=180)),
        evidence_url=f"https://example.com/vouch/{proj_ids[0]}/{legit_handle}",
    ))

    bump_projects = rng.sample(proj_ids, min(10, len(proj_ids)))
    legit_bump_pr_ids = []
    bump_start = now - timedelta(hours=3)  # within 6-hour window; old account saves it
    for i, pid in enumerate(bump_projects):
        pr_id = f"pr-{pr_counter:03d}"
        pr_counter += 1
        offset = int((i / max(len(bump_projects), 1)) * 10800)  # spread across 3 hours
        created = bump_start + timedelta(seconds=offset)
        legit_bump_pr_ids.append(pr_id)
        prs.append(PR(
            id=pr_id, project=pid, author=legit_handle,
            created_at=created,
            title=_BUMP_TITLE,
            body=_BUMP_BODY,
            diff_text=_BUMP_DIFF,
        ))

    # ------------------------------------------------------------------ #
    # 7. PLANTED (c): Brigade                                             #
    #    5 fake projects with NO real trust path denounce brigaded_handle  #
    #    An honest project vouches brigaded_handle so decision stays ACCEPT #
    # ------------------------------------------------------------------ #
    brigaded_handle = honest_handles[0]
    projects[proj_ids[0]].vouches.append(Vouch(
        handle=brigaded_handle,
        date=_iso(now - timedelta(days=120)),
        evidence_url=f"https://example.com/vouch/{proj_ids[0]}/{brigaded_handle}",
    ))
    brigade_ids = [f"fake-brigade-{i:02d}" for i in range(5)]
    for fake_pid in brigade_ids:
        projects[fake_pid] = Project(
            id=fake_pid,
            name=f"fake-brigade-project-{fake_pid[-2:]}",
            trusts=[],  # isolated -- no real project trusts or is trusted by these
            vouches=[],
            denounces=[
                Denounce(
                    handle=brigaded_handle,
                    reason_code="spam",
                    evidence_url=None,
                    date=_iso(now - timedelta(days=10)),
                    expires=None,
                )
            ],
        )

    # ------------------------------------------------------------------ #
    # 8. PLANTED (d): Sybil clique                                        #
    #    Clique vouches for sybil_spammer; clique is unreachable from net  #
    # ------------------------------------------------------------------ #
    sybil_spammer = "spammer-zed"
    accounts[sybil_spammer] = Account(
        handle=sybil_spammer,
        created_at=now - timedelta(days=rng.randint(1, 13)),
    )
    sybil_ids = [f"fake-sybil-{i:02d}" for i in range(4)]
    for i, fake_pid in enumerate(sybil_ids):
        next_sybil = sybil_ids[(i + 1) % len(sybil_ids)]
        projects[fake_pid] = Project(
            id=fake_pid,
            name=f"fake-sybil-project-{i:02d}",
            trusts=[Trust(project=next_sybil, weight=1.0)],  # circular, unreachable
            vouches=[Vouch(
                handle=sybil_spammer,
                date=_iso(now - timedelta(days=5)),
                evidence_url=None,
            )],
            denounces=[],
        )

    # A few visible PRs from the spammer
    for _ in range(3):
        pr_id = f"pr-{pr_counter:03d}"
        pr_counter += 1
        pid = rng.choice(proj_ids)
        prs.append(PR(
            id=pr_id, project=pid, author=sybil_spammer,
            created_at=now - timedelta(hours=rng.randint(1, 24)),
            title="Add comprehensive improvements",
            body=(
                "This PR adds several improvements to improve the codebase "
                "significantly and enhance overall maintainability."
            ),
            diff_text="--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n+# improvement\n",
        ))

    # ------------------------------------------------------------------ #
    # 9. PLANTED (e): Trusted Denounce -> HOLD                           #
    #    A trusted project denounces a malicious actor with evidence     #
    # ------------------------------------------------------------------ #
    denounced_handle = "malicious-actor"
    accounts[denounced_handle] = Account(
        handle=denounced_handle,
        created_at=now - timedelta(days=200),
    )
    projects[proj_ids[0]].denounces.append(Denounce(
        handle=denounced_handle,
        reason_code="malicious-backdoor",
        evidence_url=f"https://example.com/security/advisory/{denounced_handle}",
        date=_iso(now - timedelta(days=10)),
        expires=None,
    ))
    denounced_pr_id = f"pr-{pr_counter:03d}"
    pr_counter += 1
    prs.append(PR(
        id=denounced_pr_id, project=proj_ids[0], author=denounced_handle,
        created_at=now - timedelta(days=2),
        title="Security patch and dependency update",
        body="Applying routine security update to dependencies.",
        diff_text="+ # security fix\n- vulnerable_code()",
    ))

    # ------------------------------------------------------------------ #
    # 10. Assemble                                                        #
    # ------------------------------------------------------------------ #
    attack_handles = spam_handles + [sybil_spammer, denounced_handle]
    net = Network(projects=projects, accounts=accounts, prs=prs)
    labels = {
        "campaign_pr_ids": campaign_pr_ids,
        "newcomer_handles": newcomer_handles,
        "attack_handles": attack_handles,
        "brigaded_handle": brigaded_handle,
        "legit_bump_pr_ids": legit_bump_pr_ids,
        "sybil_spammer_handle": sybil_spammer,
        "trusted_denounced_handle": denounced_handle,
        "trusted_denounced_pr_id": denounced_pr_id,
    }
    return net, labels


def write_network(net: Network, labels: dict, out_dir) -> None:
    """
    Write the network to the JSON folder layout the loader expects.

        out_dir/
            projects/<id>.json   -- one file per project
            accounts.json        -- list of all accounts
            prs.json             -- list of all PRs
            labels.json          -- ground truth (engine never reads this)
    """
    out = Path(out_dir)
    proj_dir = out / "projects"
    proj_dir.mkdir(parents=True, exist_ok=True)

    def _ser_dt(obj):
        if isinstance(obj, datetime):
            return _iso(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serialisable")

    for pid, proj in net.projects.items():
        data = {
            "id": proj.id,
            "name": proj.name,
            "trusts": [{"project": t.project, "weight": t.weight}
                       for t in proj.trusts],
            "vouches": [
                {"handle": v.handle, "date": v.date, "evidence_url": v.evidence_url}
                for v in proj.vouches
            ],
            "denounces": [
                {
                    "handle": d.handle,
                    "reason_code": d.reason_code,
                    "evidence_url": d.evidence_url,
                    "date": d.date,
                    "expires": d.expires,
                }
                for d in proj.denounces
            ],
        }
        (proj_dir / f"{pid}.json").write_text(
            json.dumps(data, indent=2, default=_ser_dt)
        )

    # accounts.json
    acc_list = [
        {"handle": a.handle, "created_at": _iso(a.created_at)}
        for a in net.accounts.values()
    ]
    (out / "accounts.json").write_text(json.dumps(acc_list, indent=2))

    # prs.json
    pr_list = [
        {
            "id": pr.id,
            "project": pr.project,
            "author": pr.author,
            "created_at": _iso(pr.created_at),
            "title": pr.title,
            "body": pr.body,
            "diff_text": pr.diff_text,
        }
        for pr in net.prs
    ]
    (out / "prs.json").write_text(json.dumps(pr_list, indent=2))

    # labels.json -- ground truth for tests; the trust engine never reads this
    (out / "labels.json").write_text(json.dumps(labels, indent=2))
