"""Seeded, isolated attack experiments using the real trust engine when available."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from random import Random

from .campaigns import campaign_policy, detect


def _network(seed):
    from .models import Account, Network, PR, Project

    now = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
    rng = Random(seed)
    accounts = {f"newcomer-{i}": Account(handle=f"newcomer-{i}",
                created_at=(now - timedelta(days=rng.randint(1, 10))).isoformat())
                for i in range(15)}
    accounts["target"] = Account(handle="target", created_at=(now - timedelta(days=100)).isoformat())
    projects = {name: Project(id=name, name=name, trusts=[], vouches=[], denounces=[])
                for name in ["viewer", *[f"fake-{i}" for i in range(10)]]}
    # Distinct legitimate changes ensure newcomers participate in detection too.
    topics = ('authentication', 'pagination', 'serialization', 'localization', 'caching',
              'accessibility', 'encryption', 'compression', 'routing', 'indexing',
              'rendering', 'scheduling', 'logging', 'validation', 'formatting')
    prs = [PR(id=f'honest-{i}', project=f'fake-{i % 10}', author=f'newcomer-{i}',
              created_at=now.isoformat(), title=topic, body=topic, diff_text=topic)
           for i, topic in enumerate(topics)]
    return Network(projects=projects, accounts=accounts, prs=prs), now


def _attack(clean, now, scenario):
    from .models import Account, Denounce, PR, Trust, Vouch

    net = deepcopy(clean)
    date = now.isoformat()
    fake_projects = [project for key, project in net.projects.items() if key != "viewer"]
    for project in fake_projects:
        if scenario == "brigade-denounce":
            project.denounces.append(Denounce(handle="target", reason_code="spam",
                evidence_url="https://example.test/evidence", date=date,
                expires=(now + timedelta(days=30)).isoformat()))
        else:
            project.vouches.append(Vouch(handle="target", date=date,
                                         evidence_url="https://example.test/evidence"))
    if scenario == "sybil-clique" or scenario == "collusive-cluster":
        for project in fake_projects:
            project.trusts.extend(Trust(project=other.id, weight=1.0)
                                  for other in fake_projects if other.id != project.id)
    elif scenario == "trust-laundering":
        # Trust edges connect projects; vouches connect projects to authors.
        # Only the distant endpoint vouches, beyond the three-hop limit.
        for project in fake_projects:
            project.vouches.clear()
        chain = [net.projects["viewer"], *fake_projects[:4]]
        for source, target in zip(chain, chain[1:]):
            source.trusts.append(Trust(project=target.id, weight=1.0))
        chain[-1].vouches.append(Vouch(handle="target", date=date,
                                      evidence_url="https://example.test/evidence"))
    if scenario == "collusive-cluster":
        net.accounts["target"] = Account(handle="target", created_at=(now - timedelta(days=2)).isoformat())
        for i in range(20):
            net.prs.append(PR(id=f"attack-{i:02d}", project=f"fake-{i % 10}",
                author="target", created_at=(now + timedelta(minutes=i * 5)).isoformat(),
                title="Improve project documentation", body="Please accept this contribution to improve docs.",
                diff_text="+ documentation update"))
    return net


def markdown_table(results):
    lines = ["| Attack | Naive inflation | Defended inflation | Relative reduction | Newcomer false positives |",
             "|---|---:|---:|---:|---:|"]
    for name, row in results["scenarios"].items():
        reduction = row["relative_reduction"]
        reduction_text = "n/a" if reduction is None else f"{reduction:.1%}"
        lines.append(f"| {name} | {row['naive_inflation']:.3f} | {row['defended_inflation']:.3f} | "
                     f"{reduction_text} | {row['newcomer_false_positive_rate']:.1%} |")
    return "\n".join(lines) + "\n\n" + results['metric_note']


def run(seed=42):
    """Measure attack-induced score changes; do not assert that defenses win.

    Brigade inflation means gained disbelief; other attacks mean gained belief.
    Naive changes use naive_score's native units; defended changes use [0,1]
    belief/disbelief. Relative reduction requires matching score scales to be
    interpreted as a calibrated benchmark, not a general robustness guarantee.
    """
    from .trust import evaluate_author, naive_score

    clean, now = _network(seed)
    _, policy_hash = campaign_policy()
    results = {"seed": seed, "policy_hash": policy_hash, "scenarios": {},
               "metric_note": "Attack-induced native score changes; verify baseline scale before comparing magnitudes."}
    for name in ("brigade-denounce", "sybil-clique", "trust-laundering", "collusive-cluster"):
        before = deepcopy(clean)
        if name == "brigade-denounce":
            from .models import Vouch
            before.projects['viewer'].vouches.append(Vouch(handle='target', date=now.isoformat(),
                evidence_url='https://example.test/honest-contribution'))
        baseline_naive = naive_score(before, "target")
        baseline_defended = evaluate_author(before, "viewer", "target", now=now)
        attacked = _attack(before, now, name)
        campaigns = detect(attacked)
        handles = frozenset(author for campaign in campaigns if campaign.flagged for author in campaign.authors)
        decision = evaluate_author(attacked, "viewer", "target", campaign_handles=handles, now=now)
        naive = naive_score(attacked, "target")
        is_brigade = name == "brigade-denounce"
        naive_inflation = max(0.0, (baseline_naive - naive) if is_brigade else (naive - baseline_naive))
        field = "disbelief" if is_brigade else "belief"
        defended_inflation = max(0.0, getattr(decision, field) - getattr(baseline_defended, field))
        newcomers = [handle for handle in clean.accounts if handle.startswith("newcomer-")]
        false_positives = sum(evaluate_author(attacked, "viewer", handle,
            campaign_handles=handles, now=now).decision == "HOLD" for handle in newcomers)
        results["scenarios"][name] = dict(
            naive_before=baseline_naive, naive_after=naive,
            defended_before=getattr(baseline_defended, field), defended_after=getattr(decision, field),
            naive_inflation=naive_inflation, defended_inflation=defended_inflation,
            relative_reduction=(1 - defended_inflation / naive_inflation) if naive_inflation else None,
            newcomer_false_positive_rate=false_positives / len(newcomers),
            honest_newcomers=len(newcomers), decision=decision.decision,
            flagged_pr_ids=[pr_id for campaign in campaigns if campaign.flagged for pr_id in campaign.pr_ids],
            embedding_used=any(campaign.embedding_used for campaign in campaigns),
        )
    results["markdown"] = markdown_table(results)
    return results


if __name__ == "__main__":
    print(run()["markdown"])
