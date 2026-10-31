"""Lab orchestration tests use a small fake engine, never benchmark evidence."""
import sys
from types import ModuleType, SimpleNamespace as Record

import pytest

from test_campaigns import contract
from trustnet import lab


@pytest.fixture
def engine(contract, monkeypatch):
    module = ModuleType('trustnet.trust')
    module.naive_score = lambda net, handle: sum(
        sum(v.handle == handle for v in project.vouches)
        - sum(d.handle == handle for d in project.denounces)
        for project in net.projects.values())

    def evaluate(net, viewer, handle, campaign_handles=frozenset(), now=None):
        return Record(belief=0., disbelief=0.,
            decision='HOLD' if handle in campaign_handles else 'PROVISIONAL')
    module.evaluate_author = evaluate
    monkeypatch.setitem(sys.modules, 'trustnet.trust', module)
    return module


def test_all_four_attacks_metrics_and_markdown(engine):
    results = lab.run(42)
    assert list(results['scenarios']) == [
        'brigade-denounce', 'sybil-clique', 'trust-laundering', 'collusive-cluster']
    for row in results['scenarios'].values():
        assert row['naive_inflation'] > 0
        assert row['defended_inflation'] == 0
        assert row['relative_reduction'] == 1
        assert row['newcomer_false_positive_rate'] == 0
        assert row['honest_newcomers'] == 15
    cluster = results['scenarios']['collusive-cluster']
    assert len(cluster['flagged_pr_ids']) == 20
    assert cluster['decision'] == 'HOLD'
    assert cluster['embedding_used'] is False
    assert 'Relative reduction' in results['markdown']
    assert 'brigade-denounce' in results['markdown']
    assert results == lab.run(42)


def test_lab_reports_failed_defense_without_fabricating_a_win(engine):
    engine.evaluate_author = lambda net, viewer, handle, **kwargs: Record(
        belief=float(any(p.vouches for p in net.projects.values())),
        disbelief=float(any(p.denounces for p in net.projects.values())),
        decision='HOLD')
    results = lab.run()
    row = results['scenarios']['trust-laundering']
    assert row['defended_inflation'] == 1
    assert row['relative_reduction'] == 0
    assert row['newcomer_false_positive_rate'] == 1


def test_zero_baseline_inflation_is_not_divided_by_zero(engine):
    engine.naive_score = lambda net, handle: 0.
    result = lab.run()
    assert all(row['relative_reduction'] is None for row in result['scenarios'].values())
    assert 'n/a' in result['markdown']


def test_seeded_networks_and_attack_isolation(contract):
    clean, now = lab._network(1)
    same, _ = lab._network(1)
    other, _ = lab._network(2)
    assert clean == same and clean != other
    attacked = lab._attack(clean, now, 'trust-laundering')
    assert not any(p.trusts or p.vouches or p.denounces for p in clean.projects.values())
    assert len(attacked.projects['viewer'].trusts) == 1
    assert len(attacked.projects['fake-3'].vouches) == 1
    assert not attacked.projects['fake-0'].vouches
