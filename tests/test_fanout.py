from datetime import datetime, timedelta, timezone

import pytest
from trust_helpers import NOW, network, project

from trustnet import fanout_demo
from trustnet.campaigns import detect
from trustnet.models import Account, Campaign, Network, PR
from trustnet.trust import evaluate_author, evaluate_pr

BASE = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)


def net_of(author="u", age_days=3, count=6, minutes_apart=10, project_count=None, with_account=True):
    """One author opening `count` different PRs, each in its own project (or cycling through project_count)."""
    prs = [PR(id=f"p{i}", project=f"proj-{i % (project_count or count)}", author=author,
              created_at=(BASE + timedelta(minutes=minutes_apart * i)).isoformat(),
              title=f"unique change number {i} about topic {i * 7}", body=f"body {i}", diff_text="")
           for i in range(count)]
    accounts = {author: Account(handle=author, created_at=(BASE - timedelta(days=age_days)).isoformat())} if with_account else {}
    return Network(projects={}, accounts=accounts, prs=prs)


def behavior(net):
    return [c for c in detect(net, use_embeddings=False) if c.kind == "behavior"]


def test_a_new_account_across_many_projects_is_flagged_whatever_the_text():
    found = behavior(net_of(count=6))
    assert len(found) == 1 and found[0].flagged and found[0].authors == ["u"]
    assert found[0].pr_ids == [f"p{i}" for i in range(6)]
    assert "6 PRs in 6 projects" in found[0].evidence[0] and found[0].embedding_used is False


@pytest.mark.parametrize("case, net", [
    ("too few projects", net_of(count=4)),
    ("PRs far apart", net_of(count=6, minutes_apart=120)),   # 6 projects need 10 hours: no 6-hour window has 5
    ("old account", net_of(age_days=60)),
    ("account age unknown", net_of(with_account=False)),
    ("many PRs but few projects", net_of(count=12, project_count=3)),
    ("account created after its PRs", net_of(age_days=-1)),
])
def test_it_does_not_flag(case, net):
    assert behavior(net) == [], case


def test_the_densest_window_is_found_inside_a_longer_history():
    slow = net_of(count=20, minutes_apart=100, project_count=20)    # a new project every 100 minutes: 4 per 6 hours
    assert behavior(slow) == []
    steady = net_of(count=20, minutes_apart=60, project_count=20)   # one per hour: 7 inside a 6-hour window
    found = behavior(steady)
    assert len(found) == 1 and len(found[0].pr_ids) == 7


def test_boundary_of_five_projects_and_fourteen_days():
    assert len(behavior(net_of(count=5))) == 1 and behavior(net_of(count=4)) == []
    assert len(behavior(net_of(age_days=13.9))) == 1 and behavior(net_of(age_days=14)) == []


# --- what the engine does with the flag --------------------------------------------------------------

def flag_for(author="u", pr_ids=("p0",)):
    return Campaign(id=f"fanout-{author}", pr_ids=list(pr_ids), projects=["a"], authors=[author], score=.6,
                    flagged=True, evidence=[], embedding_used=False, kind="behavior")


def pr(pr_id="p0", author="u"):
    return PR(id=pr_id, project="V", author=author, created_at="2026-10-31T10:00:00Z", title="t", body="b", diff_text="d")


def test_an_unvouched_flagged_account_is_held():
    d = evaluate_pr(network(project("V")), "V", pr(), [flag_for()])
    assert d.decision == "HOLD" and d.in_campaign
    assert "behavior flag" in " ".join(d.reasons) and d.next_steps == []


def test_a_vouch_strong_enough_to_accept_overrides_the_behavior_flag():
    d = evaluate_pr(network(project("V", vouches=["u"])), "V", pr(), [flag_for()])
    assert d.decision == "ACCEPT" and not d.in_campaign
    assert d.ignored == ["behavior flag overridden: vouched by trusted projects (belief 0.80)"]


def test_a_weak_vouch_does_not_override_it():
    net = network(project("V", trusts={"P": 0.9}), project("P", trusts={"Q": 0.9}), project("Q", vouches=["u"]))
    assert evaluate_pr(net, "V", pr(), [flag_for()]).decision == "HOLD"      # belief 0.39 is below 0.5


def test_a_flag_on_a_different_pr_or_author_changes_nothing():
    net = network(project("V"))
    assert evaluate_pr(net, "V", pr("p9"), [flag_for(pr_ids=("p0",))]).decision == "PROVISIONAL"
    assert evaluate_pr(net, "V", pr("p0"), [flag_for(pr_ids=("p0",))]).decision == "HOLD"


def test_a_behavior_flag_does_not_cost_the_vouchers_anything():
    net = network(project("V", trusts={"P": 1.0}), project("P", vouches=["alice", "u"]))
    assert evaluate_pr(net, "V", pr("p9", author="alice"), [flag_for()]).belief == pytest.approx(0.8)


def test_a_text_campaign_flag_still_costs_vouchers_and_still_holds():
    text = Campaign(id="c", pr_ids=["p0"], projects=["a"], authors=["u"], score=1, flagged=True, evidence=[],
                    embedding_used=False)
    net = network(project("V", trusts={"P": 1.0}), project("P", vouches=["alice", "u"]))
    assert evaluate_pr(net, "V", pr("p9", author="alice"), [text]).belief == pytest.approx(0.4)
    assert evaluate_pr(network(project("V", vouches=["u"])), "V", pr(), [text]).decision == "HOLD"


# --- the demo ---------------------------------------------------------------------------------------

def test_the_demo_separates_the_three_people_without_any_text_campaign():
    result = fanout_demo.run()
    assert result["text_campaigns"] == []
    rows = {r["handle"]: r for r in result["people"]}
    assert (rows["fresh-ai-user"]["behavior_flag"], rows["fresh-ai-user"]["decision"]) == (True, "HOLD")
    assert (rows["busy-maintainer"]["behavior_flag"], rows["busy-maintainer"]["decision"]) == (False, "ACCEPT")
    assert (rows["eager-newcomer"]["behavior_flag"], rows["eager-newcomer"]["decision"]) == (True, "ACCEPT")
