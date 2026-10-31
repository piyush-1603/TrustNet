"""Connected PR clusters and deterministic campaign evidence."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from importlib import import_module
import json

from .similarity import similarity_matrices


# shortcut: shared policy loader is not merged; remove defaults after integration.
DEFAULTS = dict(similarity_threshold=0.85, embedding_threshold=0.80, min_prs=8, min_projects=5, fanout_min_projects=5,
                window_hours=6, min_young_share=0.7, young_days=14,
                flag_threshold=0.6, size_scale=20, projects_scale=10,
                size_weight=0.4, projects_weight=0.3, young_weight=0.3)


def campaign_policy():
    """Shared loader may return a policy dict or (policy, hash)."""
    digest = None
    try:
        loaders = import_module("trustnet.loaders")
    except ModuleNotFoundError as exc:
        if exc.name != "trustnet.loaders":
            raise
        policy = {"campaigns": DEFAULTS}
    else:
        policy = loaders.load_policy()
        if isinstance(policy, tuple):
            policy, digest = policy
    settings = {**DEFAULTS, **policy.get("campaigns", {})}
    if digest is None:
        digest = sha256(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return settings, digest


MAX_TEXT = 1500   # characters sent for comparison, so a 1,000-line change cannot drown the description
DIFF_LINES = 20   # changed lines kept from the code change


def pr_text(pr):
    """Short, fixed-size text for comparing PRs: title and description first, then a thin view of the change.

    The description is what a person (or a spammer) writes to say what the PR is for. The code change
    adds only the changed file names and the first few changed lines, so its size does not matter.
    """
    lines = (pr.diff_text or "").splitlines()
    files = [line[6:] for line in lines if line.startswith("+++ b/")][:10]
    changed = [line for line in lines if line[:1] in ("+", "-") and not line.startswith(("+++", "---"))]
    parts = [pr.title, pr.body, "files: " + ", ".join(files) if files else "", *changed[:DIFF_LINES]]
    return "\n".join(part for part in parts if part)[:MAX_TEXT]


def _time(value):
    result = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("campaign timestamps must include a timezone")
    return result.astimezone(timezone.utc)


def detect_fanout(net, policy, policy_hash):
    """Text-independent signal: one new account opening PRs in many projects within a few hours.

    For each author, take the window of `window_hours` that touches the most distinct projects. If it
    reaches `fanout_min_projects` and the account was under `young_days` old at the window's first PR,
    the author is flagged. Unknown account age is never flagged. How the viewer treats a flag is decided
    in trust.py (a strong vouch from a trusted project overrides it).
    """
    from .models import Campaign

    by_author = defaultdict(list)
    for pr in net.prs:
        by_author[pr.author].append(pr)
    window = timedelta(hours=policy["window_hours"])
    found = []
    for author, prs in sorted(by_author.items()):
        account = net.accounts.get(author)
        if account is None:
            continue
        prs = sorted(prs, key=lambda pr: (_time(pr.created_at), str(pr.id)))
        times = [_time(pr.created_at) for pr in prs]
        best, start = [], 0
        for end in range(len(prs)):
            while times[end] - times[start] > window:
                start += 1
            if len({pr.project for pr in prs[start:end + 1]}) > len({pr.project for pr in best}):
                best = prs[start:end + 1]
        projects = sorted({pr.project for pr in best})
        if len(projects) < policy["fanout_min_projects"]:
            continue
        first = _time(best[0].created_at)
        age = (first - _time(account.created_at)).total_seconds() / 86400
        if not 0 <= age < policy["young_days"]:
            continue
        minutes = round((_time(best[-1].created_at) - first).total_seconds() / 60)
        ids = [pr.id for pr in best]
        found.append(Campaign(
            id=f"fanout-{author}", pr_ids=ids, projects=projects, authors=[author],
            score=min(1.0, len(projects) / policy["projects_scale"]), flagged=True,
            evidence=[f"{author}: {len(ids)} PRs in {len(projects)} projects within {minutes // 60}h{minutes % 60:02d}m, "
                      f"account {age:.0f} days old (text-independent behavior flag)",
                      f"policy_hash={policy_hash}"],
            embedding_used=False, kind="behavior"))
    return found


def detect(net, use_embeddings=True):
    """Keep qualifying connected components; age share counts distinct authors.

    A component's full time span must fit the policy window. For repeat authors,
    account age is measured at their earliest PR in the component.
    """
    from .models import Campaign

    policy, policy_hash = campaign_policy()
    prs = sorted(net.prs, key=lambda pr: str(pr.id))
    if not prs:
        return []
    keyword, embedding = similarity_matrices([pr_text(pr) for pr in prs], use_embeddings)
    embedding_used = embedding is not None
    parents = list(range(len(prs)))

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    for i in range(len(prs)):
        for j in range(i):
            if (keyword[i, j] >= policy["similarity_threshold"]
                    or (embedding_used and embedding[i, j] >= policy["embedding_threshold"])):
                parents[root(i)] = root(j)
    groups = {}
    for i, pr in enumerate(prs):
        groups.setdefault(root(i), []).append(pr)

    found = []
    for group in groups.values():
        projects = sorted({pr.project for pr in group})
        if len(group) < policy["min_prs"] or len(projects) < policy["min_projects"]:
            continue
        times = [_time(pr.created_at) for pr in group]
        hours = (max(times) - min(times)).total_seconds() / 3600
        if hours > policy["window_hours"]:
            continue
        first_pr = {}
        for pr, when in zip(group, times):
            first_pr[pr.author] = min(first_pr.get(pr.author, when), when)
        young_authors = set()
        for author, when in first_pr.items():
            account = net.accounts.get(author)
            if account is not None:
                age = (when - _time(account.created_at)).total_seconds() / 86400
                if 0 <= age < policy["young_days"]:
                    young_authors.add(author)
        share = len(young_authors) / len(first_pr)
        if share < policy["min_young_share"]:
            continue
        score = (policy["size_weight"] * min(1, len(group) / policy["size_scale"])
                 + policy["projects_weight"] * min(1, len(projects) / policy["projects_scale"])
                 + policy["young_weight"] * share)
        # Similar text alone must not sweep in established accounts: only new accounts are campaign members.
        ids = [pr.id for pr in group if pr.author in young_authors]
        link_rule = f"keyword similarity >= {policy['similarity_threshold']}"
        if embedding_used:
            link_rule += f" or model similarity >= {policy['embedding_threshold']}"
        identifier = sha256(json.dumps(ids).encode()).hexdigest()[:12]
        minutes = round(hours * 60)
        found.append(Campaign(
            id=f"campaign-{identifier}", pr_ids=ids, projects=projects,
            authors=sorted(young_authors), score=score, flagged=score >= policy["flag_threshold"],
            evidence=[f"{len(group)} PRs, {len(projects)} projects, {minutes // 60}h{minutes % 60:02d}m window, "
                      f"{share:.0%} accounts under {policy['young_days']} days",
                      f"Connected by {link_rule}; embedding_used={str(embedding_used).lower()}",
                      f"policy_hash={policy_hash}"],
            embedding_used=embedding_used,
        ))
    return found + detect_fanout(net, policy, policy_hash)
