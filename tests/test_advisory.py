import json

import pytest
from trust_helpers import NOW, network, project

from trustnet.advisory import FORMAT, build_advisory, load_advisory
from trustnet.models import Campaign, PR
from trustnet.trust import evaluate_author, evaluate_pr


def campaign(flagged=True, authors=("bot-1", "bot-2")):
    return Campaign(id="c-1", pr_ids=["pr-1", "pr-2"], projects=["P", "Q"], authors=list(authors), score=0.9,
                    flagged=flagged, evidence=["2 PRs"], embedding_used=True)


def advisory(issuer="ISSUER", authors=("bot-1",)):
    return {"format": FORMAT, "issuer": issuer, "campaigns": [{"id": "c-1", "authors": list(authors)}]}


# --- the file ------------------------------------------------------------------------------------

def test_build_lists_only_flagged_campaigns_and_no_pr_text():
    adv = build_advisory("proj-01", [campaign(), campaign(flagged=False)], "abc123", now=NOW)
    assert adv["format"] == FORMAT and adv["issuer"] == "proj-01" and adv["policy_hash"] == "abc123"
    assert len(adv["campaigns"]) == 1 and adv["campaigns"][0]["authors"] == ["bot-1", "bot-2"]
    assert set(adv["campaigns"][0]) == {"id", "kind", "authors", "pr_ids", "projects", "score", "evidence", "embedding_used"}


def test_round_trip_through_a_file(tmp_path):
    path = tmp_path / "adv.json"
    path.write_text(json.dumps(build_advisory("proj-01", [campaign()], "abc123", now=NOW)))
    assert load_advisory(path)["campaigns"][0]["id"] == "c-1"


@pytest.mark.parametrize("bad, message", [
    ("{", "cannot read advisory"),
    (json.dumps({"format": "other", "issuer": "x", "campaigns": []}), "not a trustnet-advisory/1 file"),
    (json.dumps({"format": FORMAT, "issuer": "", "campaigns": []}), "'issuer'"),
    (json.dumps({"format": FORMAT, "issuer": "x", "campaigns": "no"}), "'campaigns' must be a list"),
    (json.dumps({"format": FORMAT, "issuer": "x", "campaigns": [{"id": "c", "authors": [1]}]}), r"campaigns\[0\]"),
])
def test_load_rejects_malformed_files(tmp_path, bad, message):
    path = tmp_path / "adv.json"
    path.write_text(bad)
    with pytest.raises(ValueError, match=message):
        load_advisory(path)


# --- how the engine uses it ------------------------------------------------------------------------

def test_an_advisory_from_a_trusted_project_holds_the_listed_author():
    net = network(project("V", trusts={"ISSUER": 0.9}), project("ISSUER"))
    d = evaluate_author(net, "V", "bot-1", now=NOW, advisories=[advisory()])
    assert d.decision == "HOLD" and d.in_campaign
    assert "listed in campaign advisory c-1 from ISSUER (trust 0.90" in " ".join(d.reasons)
    assert ["V", "ISSUER"] in d.paths


def test_an_advisory_from_an_untrusted_project_is_ignored():
    net = network(project("V"), project("ISSUER"))
    d = evaluate_author(net, "V", "bot-1", now=NOW, advisories=[advisory()])
    assert d.decision == "PROVISIONAL" and not d.in_campaign
    assert d.ignored == ["ignored: advisory from ISSUER (source not trusted)"]


def test_an_advisory_does_not_touch_authors_it_does_not_list():
    net = network(project("V", trusts={"ISSUER": 1}, vouches=["alice"]), project("ISSUER"))
    d = evaluate_author(net, "V", "alice", now=NOW, advisories=[advisory()])
    assert d.decision == "ACCEPT" and d.ignored == []


def test_a_far_away_issuer_is_trusted_less_and_can_fall_below_the_cutoff():
    net = network(project("V", trusts={"A": 0.5}), project("A", trusts={"ISSUER": 0.5}), project("ISSUER"))
    assert evaluate_author(net, "V", "bot-1", now=NOW, advisories=[advisory()]).decision == "PROVISIONAL"  # 0.15


def test_evaluate_pr_passes_advisories_through():
    net = network(project("V", trusts={"ISSUER": 1}), project("ISSUER"))
    pr = PR(id="pr-9", project="V", author="bot-1", created_at="2026-10-31T10:00:00Z", title="t", body="b", diff_text="d")
    assert evaluate_pr(net, "V", pr, [], advisories=[advisory()]).decision == "HOLD"
    assert evaluate_pr(net, "V", pr, []).decision == "PROVISIONAL"


def test_an_advisory_from_a_trusted_project_also_discounts_projects_that_vouched_for_listed_accounts():
    net = network(project("V", trusts={"ISSUER": 1, "P": 1}), project("ISSUER"), project("P", vouches=["alice", "bot-1"]))
    d = evaluate_author(net, "V", "alice", now=NOW, advisories=[advisory()])
    assert d.belief == pytest.approx(0.4) and "discounted: P" in d.ignored[0]
    far = network(project("V", trusts={"P": 1}), project("ISSUER"), project("P", vouches=["alice", "bot-1"]))
    assert evaluate_author(far, "V", "alice", now=NOW, advisories=[advisory()]).belief == pytest.approx(0.8)
