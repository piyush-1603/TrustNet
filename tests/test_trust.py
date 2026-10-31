import pytest
from trust_helpers import NOW, denounce, network, project

from trustnet.models import Campaign, PR
from trustnet.trust import evaluate_author, evaluate_pr, naive_score, project_trust


def chain(*weights):
    """P0 -> P1 -> ... with the given edge weights."""
    return network(*[project(f"P{i}", trusts={f"P{i + 1}": weights[i]} if i < len(weights) else None)
                     for i in range(len(weights) + 1)])


# --- If A trusts B and B trusts C, how much does A trust C? -------------------------------------

def test_direct_trust_is_the_edge_weight():
    assert project_trust(chain(0.9), "P0", "P1") == (pytest.approx(0.9), ["P0", "P1"])


def test_transitive_trust_decays_per_extra_hop():
    value, path = project_trust(chain(0.9, 0.9), "P0", "P2")
    assert value == pytest.approx(0.9 * 0.9 * 0.6) == pytest.approx(0.486)
    assert path == ["P0", "P1", "P2"]


def test_three_hops_count_but_four_do_not():
    assert project_trust(chain(1, 1, 1), "P0", "P3")[0] == pytest.approx(0.36)
    assert project_trust(chain(1, 1, 1, 1), "P0", "P4") == (0.0, [])


def test_trust_below_the_minimum_counts_as_none():
    assert project_trust(chain(0.8, 0.8), "P0", "P2")[0] == pytest.approx(0.384)
    assert project_trust(chain(0.8, 0.8, 0.8), "P0", "P3") == (0.0, [])  # 0.184 < 0.25


def test_a_project_trusts_itself_fully():
    assert project_trust(chain(0.5), "P0", "P0") == (1.0, ["P0"])


def test_unknown_or_unreachable_projects_get_no_trust():
    assert project_trust(chain(0.9), "P0", "nope") == (0.0, [])
    assert project_trust(chain(0.9), "P1", "P0") == (0.0, [])  # trust has a direction


def test_trust_cycles_terminate():
    net = network(project("A", trusts={"B": 1}), project("B", trusts={"A": 1, "C": 1}), project("C"))
    assert project_trust(net, "A", "C") == (pytest.approx(0.6), ["A", "B", "C"])


def test_strongest_path_wins_and_paths_are_never_added():
    net = network(project("A", trusts={"B": 1, "C": 1, "D": 0.5}), project("B", trusts={"D": 1}),
                  project("C", trusts={"D": 1}), project("D"))
    value, path = project_trust(net, "A", "D")
    assert value == pytest.approx(0.6)  # two equal 0.6 paths, not 1.2 and not the direct 0.5
    assert path == ["A", "B", "D"]  # tie broken by name, so results repeat exactly
    net.projects["A"].trusts[2].weight = 0.7
    assert project_trust(net, "A", "D") == (pytest.approx(0.7), ["A", "D"])


# --- A newcomer, and what a vouch is worth ---------------------------------------------------------

def test_a_newcomer_nobody_has_spoken_about_is_provisional_never_held():
    d = evaluate_author(network(project("V")), "V", "newcomer", now=NOW)
    assert (d.decision, d.belief, d.disbelief, d.uncertainty) == ("PROVISIONAL", 0.0, 0.0, 1.0)
    assert "not a rejection" in " ".join(d.reasons)


def test_a_vouch_from_the_viewer_itself_is_accepted():
    d = evaluate_author(network(project("V", vouches=["alice"])), "V", "alice", now=NOW)
    assert d.decision == "ACCEPT" and d.belief == pytest.approx(0.8) and d.paths == [["V"]]


def test_a_vouch_two_hops_away_is_not_enough_alone_but_two_are():
    one = network(project("V", trusts={"P": 0.9}), project("P", trusts={"Q1": 0.9}),
                  project("Q1", vouches=["alice"]))
    d = evaluate_author(one, "V", "alice", now=NOW)
    assert d.decision == "PROVISIONAL" and d.belief == pytest.approx(0.8 * 0.486)
    two = network(project("V", trusts={"P": 0.9}), project("P", trusts={"Q1": 0.9, "Q2": 0.9}),
                  project("Q1", vouches=["alice"]), project("Q2", vouches=["alice"]))
    d = evaluate_author(two, "V", "alice", now=NOW)
    assert d.decision == "ACCEPT" and d.belief == pytest.approx(1 - (1 - 0.8 * 0.486) ** 2)
    assert d.paths == [["V", "P", "Q1"], ["V", "P", "Q2"]]


def test_only_the_strongest_three_sources_count():
    projects = [project("V", trusts={f"S{i}": 1 for i in range(5)})]
    projects += [project(f"S{i}", vouches=["alice"]) for i in range(5)]
    d = evaluate_author(network(*projects), "V", "alice", now=NOW)
    assert d.belief == pytest.approx(1 - 0.2 ** 3)
    assert sum("not counted" in line for line in d.ignored) == 2


def test_a_vouch_from_a_project_the_viewer_does_not_trust_is_ignored():
    d = evaluate_author(network(project("V"), project("X", vouches=["alice"])), "V", "alice", now=NOW)
    assert d.decision == "PROVISIONAL" and d.belief == 0.0
    assert d.ignored == ["ignored: source not trusted: X (vouch)"]


def test_two_viewpoints_give_two_answers_for_the_same_author():
    net = network(project("P", vouches=["alice"]), project("V1", trusts={"P": 1}), project("V2"))
    assert evaluate_author(net, "V1", "alice", now=NOW).decision == "ACCEPT"
    assert evaluate_author(net, "V2", "alice", now=NOW).decision == "PROVISIONAL"


# --- How do you stop fake denounces? ---------------------------------------------------------------

def test_five_untrusted_projects_denouncing_an_honest_author_change_nothing():
    fakes = [project(f"F{i}", trusts={f"F{j}": 1 for j in range(5) if j != i}, denounces=[denounce("alice")])
             for i in range(5)]
    net = network(project("V", vouches=["alice"]), *fakes)
    d = evaluate_author(net, "V", "alice", now=NOW)
    assert d.decision == "ACCEPT" and d.disbelief == 0.0
    assert len(d.ignored) == 5 and all(line.startswith("ignored: source not trusted") for line in d.ignored)


def test_a_trusted_denounce_with_evidence_holds_the_author():
    d = evaluate_author(network(project("V", denounces=[denounce("bot")])), "V", "bot", now=NOW)
    assert d.decision == "HOLD" and d.disbelief == pytest.approx(0.8)


def test_a_denounce_without_evidence_counts_half():
    net = network(project("V", denounces=[denounce("bot", evidence=None)]))
    d = evaluate_author(net, "V", "bot", now=NOW)
    assert d.disbelief == pytest.approx(0.4) and d.decision == "PROVISIONAL"
    assert d.ignored == ["halved: no evidence link in denounce from V"]


def test_an_expired_denounce_is_ignored_until_it_is_expired():
    net = network(project("V", denounces=[denounce("bot", expires="2026-10-31T11:00:00Z")]))
    assert evaluate_author(net, "V", "bot", now=NOW).decision == "PROVISIONAL"
    assert evaluate_author(net, "V", "bot", now=NOW).ignored == ["ignored: expired denounce from V"]
    assert evaluate_author(net, "V", "bot", now="2026-10-31T10:00:00Z").decision == "HOLD"


def test_a_weakly_trusted_denounce_alone_does_not_hold():
    net = network(project("V", trusts={"D": 0.4}), project("D", denounces=[denounce("bot")]))
    d = evaluate_author(net, "V", "bot", now=NOW)
    assert d.disbelief == pytest.approx(0.32) and d.decision == "PROVISIONAL"


def test_a_strong_denounce_beats_a_weak_vouch():
    net = network(project("V", trusts={"P": 0.9}, denounces=[denounce("x")]), project("P", trusts={"Q": 0.9}),
                  project("Q", vouches=["x"]))
    d = evaluate_author(net, "V", "x", now=NOW)
    assert d.belief == pytest.approx(0.8 * 0.486) and d.disbelief == pytest.approx(0.8) and d.decision == "HOLD"


# --- Campaigns ------------------------------------------------------------------------------------

def test_a_campaign_member_is_held_even_when_vouched():
    d = evaluate_author(network(project("V", vouches=["alice"])), "V", "alice", frozenset({"alice"}), now=NOW)
    assert d.decision == "HOLD" and d.in_campaign and d.belief == pytest.approx(0.8)


def pr(pr_id, author="alice", created="2026-10-31T10:00:00Z"):
    return PR(id=pr_id, project="V", author=author, created_at=created, title="t", body="b", diff_text="d")


def campaign(pr_ids, flagged=True):
    return Campaign(id="c", pr_ids=pr_ids, projects=["V"], authors=["alice"], score=0.9, flagged=flagged,
                    evidence=[], embedding_used=False)


def test_evaluate_pr_holds_only_prs_that_belong_to_a_flagged_campaign():
    net = network(project("V", vouches=["alice"]))
    inside = evaluate_pr(net, "V", pr("pr-1"), [campaign(["pr-1"])])
    assert inside.decision == "HOLD" and inside.in_campaign and inside.pr_id == "pr-1"
    assert evaluate_pr(net, "V", pr("pr-2"), [campaign(["pr-1"])]).decision == "ACCEPT"
    assert evaluate_pr(net, "V", pr("pr-1"), [campaign(["pr-1"], flagged=False)]).decision == "ACCEPT"


def test_evaluate_pr_judges_expiry_as_of_the_pr_time():
    net = network(project("V", denounces=[denounce("alice", expires="2026-10-31T11:00:00Z")]))
    assert evaluate_pr(net, "V", pr("a", created="2026-10-31T10:00:00Z"), []).decision == "HOLD"
    assert evaluate_pr(net, "V", pr("b", created="2026-10-31T12:00:00Z"), []).decision == "PROVISIONAL"


# --- Baseline and repeatability ------------------------------------------------------------------

def test_naive_score_counts_projects_equally():
    net = network(project("A", vouches=["x"]), project("B", vouches=["x"]), project("C", vouches=["x"]),
                  project("D", denounces=[denounce("x"), denounce("x")]), project("E"))
    assert naive_score(net, "x") == 2.0
    assert naive_score(net, "nobody") == 0.0


def test_results_repeat_exactly():
    net = network(project("V", trusts={"P": 0.9, "Q": 0.9}), project("P", vouches=["a"]),
                  project("Q", vouches=["a"]))
    assert evaluate_author(net, "V", "a", now=NOW) == evaluate_author(net, "V", "a", now=NOW)
