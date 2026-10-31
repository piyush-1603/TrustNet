"""Trust engine: project-to-project trust, then ACCEPT / PROVISIONAL / HOLD for one author.

Every decision is made from one project's point of view (the "viewer"), using only
public vouch/denounce lists. Thresholds come from policy.json; see docs/PLAN.md.
"""

from datetime import datetime, timezone
from functools import lru_cache

from .loaders import load_policy
from .models import Decision, parse_time


@lru_cache(maxsize=1)
def _default_policy():
    return load_policy()[0]


def _cfg(policy):
    return policy if policy is not None else _default_policy()


def project_trust(net, viewer, target, policy=None):
    """Return (trust, path): how much `viewer` trusts project `target`, and the path used.

    trust = product of edge weights * decay^(hops-1) along the single best path.
    At most max_hops hops; a result below min_trust counts as no trust: (0.0, []).
    The best path wins; paths are never added together, so fake nodes add nothing.
    """
    cfg = _cfg(policy)["trust"]
    if viewer == target:
        return 1.0, [viewer]
    best = None  # (key, value, path); the smaller key wins

    def walk(path, product):
        nonlocal best
        project = net.projects.get(path[-1])
        if project is None or len(path) - 1 >= cfg["max_hops"]:
            return
        for edge in project.trusts:
            if edge.project in path:  # simple paths only, so cycles end
                continue
            hops = len(path)
            new_product = product * edge.weight
            value = new_product * cfg["decay"] ** (hops - 1)
            if value <= 0 or value < cfg["min_trust"]:
                continue  # more hops can only lower it
            new_path = path + [edge.project]
            if edge.project == target:
                key = (-round(value, 12), hops, new_path)  # best value, then fewer hops, then name order
                if best is None or key < best[0]:
                    best = (key, value, new_path)
            else:
                walk(new_path, new_product)

    walk([viewer], 1.0)
    return (best[1], best[2]) if best else (0.0, [])


def _combine(contributions, top_k):
    """1 - prod(1 - c) over the strongest `top_k` contributions (each is (c, project, path))."""
    ranked = sorted(contributions, key=lambda item: (-item[0], item[1]))
    value = 1.0
    for c, _, _ in ranked[:top_k]:
        value *= 1 - c
    return 1 - value, ranked[:top_k], ranked[top_k:]


def evaluate_author(net, viewer, handle, campaign_handles=frozenset(), now=None, policy=None, pr_id=None):
    """Decide what `viewer` should do with `handle`.

    belief b    = 1 - prod(1 - vouch_weight * T)      over the strongest top_k trusted vouchers
    disbelief d = 1 - prod(1 - vouch_weight * T * e)  over trusted, unexpired denouncers
                  (e = 1 with an evidence link, no_evidence_factor without)
    HOLD if d >= hold_threshold and d > b, else ACCEPT if b >= accept_threshold, else PROVISIONAL.
    T = project_trust(viewer, source); records from sources below min_trust are ignored, so an author
    that no trusted project has spoken about is unknown (PROVISIONAL), never HOLD. A member of a
    flagged campaign is HOLD.
    """
    cfg = _cfg(policy)
    trust_cfg, decision_cfg = cfg["trust"], cfg["decision"]
    now = parse_time(now) if now is not None else datetime.now(timezone.utc)
    ignored, vouches, denounces = [], [], []
    for pid in sorted(net.projects):
        project = net.projects[pid]
        vouched = [v for v in project.vouches if v.handle == handle]
        denounced = [d for d in project.denounces if d.handle == handle]
        if not vouched and not denounced:
            continue
        trust, path = project_trust(net, viewer, pid, cfg)
        if trust < trust_cfg["min_trust"]:
            kinds = " and ".join(kind for kind, present in (("vouch", vouched), ("denounce", denounced)) if present)
            ignored.append(f"ignored: source not trusted: {pid} ({kinds})")
            continue
        if vouched:
            vouches.append((trust_cfg["vouch_weight"] * trust, pid, path))
        if denounced:
            active = [d for d in denounced if d.expires is None or parse_time(d.expires) > now]
            if not active:
                ignored.append(f"ignored: expired denounce from {pid}")
                continue
            factor = 1.0 if any(d.evidence_url for d in active) else trust_cfg["no_evidence_factor"]
            if factor < 1.0:
                ignored.append(f"halved: no evidence link in denounce from {pid}")
            denounces.append((trust_cfg["vouch_weight"] * trust * factor, pid, path))

    k = trust_cfg["top_k"]
    belief, used_vouches, extra_vouches = _combine(vouches, k)
    disbelief, used_denounces, extra_denounces = _combine(denounces, k)
    for _, pid, _ in extra_vouches + extra_denounces:
        ignored.append(f"not counted: {pid} is beyond the strongest {k} sources")
    uncertainty = max(0.0, 1 - belief - disbelief)

    reasons = [f"vouched by {pid} (strength {c:.2f}, path {' > '.join(path)})" for c, pid, path in used_vouches]
    reasons += [f"denounced by {pid} (strength {c:.2f}, path {' > '.join(path)})" for c, pid, path in used_denounces]
    in_campaign = handle in campaign_handles
    if in_campaign:
        decision = "HOLD"
        reasons.append("member of a flagged spam campaign")
    elif disbelief >= decision_cfg["hold_threshold"] and disbelief > belief:
        decision = "HOLD"
        reasons.append(f"disbelief {disbelief:.2f} is at least {decision_cfg['hold_threshold']} and above belief {belief:.2f}")
    elif belief >= decision_cfg["accept_threshold"]:
        decision = "ACCEPT"
        reasons.append(f"belief {belief:.2f} is at least {decision_cfg['accept_threshold']}")
    else:
        decision = "PROVISIONAL"
        reasons.append("unknown to the projects this viewer trusts: provisional review, not a rejection"
                       if not used_vouches and not used_denounces else
                       f"belief {belief:.2f} is below {decision_cfg['accept_threshold']}: provisional review")
    return Decision(pr_id=pr_id, viewer=viewer, author=handle, decision=decision, belief=belief,
                    disbelief=disbelief, uncertainty=uncertainty, reasons=reasons,
                    paths=[path for _, _, path in used_vouches + used_denounces], ignored=ignored,
                    in_campaign=in_campaign)


def evaluate_pr(net, viewer, pr, campaigns, now=None, policy=None):
    """Decide on one PR's author. The author is HOLD only if a flagged campaign contains this PR.

    `now` defaults to the PR's own time, so expiry is judged as of the PR and results repeat exactly.
    """
    flagged = any(c.flagged and pr.id in c.pr_ids for c in campaigns)
    return evaluate_author(net, viewer, pr.author, frozenset([pr.author]) if flagged else frozenset(),
                           now=now if now is not None else pr.created_at, policy=policy, pr_id=pr.id)


def naive_score(net, handle):
    """Baseline for the attack lab: projects that vouch minus projects that denounce, all counted equally."""
    vouching = sum(any(v.handle == handle for v in p.vouches) for p in net.projects.values())
    denouncing = sum(any(d.handle == handle for d in p.denounces) for p in net.projects.values())
    return float(vouching - denouncing)
