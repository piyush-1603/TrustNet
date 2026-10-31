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


def naive_decision(score):
    """Map the raw-count baseline to the same decision categories as TrustNet."""
    return "ACCEPT" if score > 0 else "HOLD" if score < 0 else "PROVISIONAL"


def attack_success(scenario, before, after):
    """Brigades must flip acceptance; promotion attacks must gain acceptance."""
    if scenario == "brigade-denounce":
        return before == "ACCEPT" and after == "HOLD"
    return before != "ACCEPT" and after == "ACCEPT"


def markdown_table(results):
    lines = ["| Attack | Naive BEFORE → AFTER | Defended BEFORE → AFTER | Naive attack success | Defended attack success | Defense goal met | Campaign false positives | Newcomer HOLD rate |",
             "|---|---|---|---|---|---|---|---|"]
    for name, row in results["scenarios"].items():
        lines.append(f"| {name} | {row['naive_before']} → {row['naive_after']} | "
                     f"{row['defended_before']} → {row['defended_after']} | "
                     f"{row['naive_attack_success']} | {row['defended_attack_success']} | "
                     f"{row['defense_goal_met']} | {row['campaign_false_positive_rate']:.1%} | "
                     f"{row['newcomer_hold_rate']:.1%} |")
    return "\n".join(lines) + "\n\n" + results['metric_note']


def run(seed=42, use_embeddings=True):
    """Compare categorical transitions on identical before/after networks.

    These seeded synthetic cases are regression evidence, not population attack
    success rates. Promotion success requires a new ACCEPT. Campaign defense
    additionally requires a flagged affected PR and PR-specific HOLD.
    """
    from .models import PR, Trust, Vouch
    from .trust import evaluate_author, evaluate_pr, naive_score

    clean, now = _network(seed)
    _, policy_hash = campaign_policy()
    results = {"seed": seed, "policy_hash": policy_hash, "scenarios": {},
               "metric_note": "Categorical outcomes on synthetic fixtures, not calibrated robustness rates. "
               "Campaign false positives count honest newcomer PRs flagged; HOLD rate counts all newcomer "
               "PR HOLD decisions. Trusted-source compromise is an intentional defense-failure control."}
    for name in ("brigade-denounce", "sybil-clique", "trust-laundering", "collusive-cluster",
                 "trusted-source-compromise"):
        before = deepcopy(clean)
        if name == "brigade-denounce":
            before.projects['viewer'].vouches.append(Vouch(handle='target', date=now.isoformat(),
                evidence_url='https://example.test/honest-contribution'))
        # Keep a target PR in both snapshots so collusion compares the same PR.
        target_pr = PR(id="attack-00", project="fake-0", author="target",
                       created_at=now.isoformat(), title="Improve project documentation",
                       body="Please accept this contribution to improve docs.", diff_text="+ documentation update")
        if name == "collusive-cluster":
            before.prs.append(target_pr)
        baseline_campaigns = detect(before, use_embeddings)
        baseline_defended = (evaluate_pr(before, "viewer", target_pr, baseline_campaigns, now=now)
                             if name == "collusive-cluster" else
                             evaluate_author(before, "viewer", "target", now=now))
        attacked = _attack(before, now, name)
        if name == "collusive-cluster":
            # _attack generates attack-00 too; retain just one instance.
            attacked.prs = [pr for pr in attacked.prs if pr.id != target_pr.id] + [target_pr]
        if name == "trusted-source-compromise":
            attacked.projects["viewer"].trusts.append(Trust(project="fake-0", weight=1.0))
        campaigns = detect(attacked, use_embeddings)
        decision = (evaluate_pr(attacked, "viewer", target_pr, campaigns, now=now)
                    if name == "collusive-cluster" else
                    evaluate_author(attacked, "viewer", "target", now=now))
        naive_before = naive_decision(naive_score(before, "target"))
        naive_after = naive_decision(naive_score(attacked, "target"))
        newcomers = [pr for pr in attacked.prs if pr.author.startswith("newcomer-")]
        newcomer_decisions = [evaluate_pr(attacked, "viewer", pr, campaigns, now=now) for pr in newcomers]
        flagged_ids = sorted({pr_id for campaign in campaigns if campaign.flagged for pr_id in campaign.pr_ids})
        defended_success = attack_success(name, baseline_defended.decision, decision.decision)
        goal = (decision.decision == "ACCEPT" if name == "brigade-denounce" else
                decision.in_campaign and decision.decision == "HOLD" if name == "collusive-cluster" else
                decision.decision != "ACCEPT")
        results["scenarios"][name] = dict(
            naive_before=naive_before, naive_after=naive_after,
            defended_before=baseline_defended.decision, defended_after=decision.decision,
            naive_attack_success=attack_success(name, naive_before, naive_after),
            defended_attack_success=defended_success, defense_goal_met=goal,
            campaign_false_positive_rate=sum(pr.id in flagged_ids for pr in newcomers) / len(newcomers),
            newcomer_hold_rate=sum(d.decision == "HOLD" for d in newcomer_decisions) / len(newcomers),
            honest_newcomers=len(newcomers), decision=decision.decision,
            target_pr_id=target_pr.id if name == "collusive-cluster" else None,
            in_campaign=decision.in_campaign, flagged_pr_ids=flagged_ids,
            embedding_used=any(campaign.embedding_used for campaign in campaigns),
        )
    results["markdown"] = markdown_table(results)
    return results


if __name__ == "__main__":
    print(run()["markdown"])
