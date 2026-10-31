"""Decision benchmark regression checks against production models and engine."""
from copy import deepcopy

import pytest

from trustnet import lab
from trustnet.models import Denounce
from trustnet.trust import evaluate_pr


@pytest.mark.parametrize('score,expected', [(2, 'ACCEPT'), (-1, 'HOLD'), (0, 'PROVISIONAL')])
def test_naive_decision(score, expected):
    assert lab.naive_decision(score) == expected


def test_production_benchmark():
    result = lab.run(use_embeddings=False)
    assert result == lab.run(use_embeddings=False)
    rows = result['scenarios']
    brigade = rows['brigade-denounce']
    assert (brigade['naive_before'], brigade['naive_after']) == ('ACCEPT', 'HOLD')
    assert (brigade['defended_before'], brigade['defended_after']) == ('ACCEPT', 'ACCEPT')
    for name, row in rows.items():
        assert row['naive_attack_success']
        assert row['defended_attack_success'] == (name == 'trusted-source-compromise')
        assert row['defense_goal_met'] == (name != 'trusted-source-compromise')
        assert row['campaign_false_positive_rate'] == row['newcomer_hold_rate'] == 0
        assert row['embedding_used'] is False
        assert 'relative_reduction' not in row
    cluster = rows['collusive-cluster']
    assert cluster['defended_after'] == 'HOLD' and cluster['in_campaign']
    assert cluster['target_pr_id'] in cluster['flagged_pr_ids']
    assert len(cluster['flagged_pr_ids']) == 20
    assert 'BEFORE → AFTER' in result['markdown']


def test_attack_success_requires_transition():
    assert not lab.attack_success('sybil-clique', 'ACCEPT', 'ACCEPT')
    assert not lab.attack_success('brigade-denounce', 'PROVISIONAL', 'HOLD')
    assert lab.attack_success('brigade-denounce', 'ACCEPT', 'HOLD')


def test_seeded_network_and_attack_isolation():
    clean, now = lab._network(1)
    same, _ = lab._network(1)
    other, _ = lab._network(2)
    assert clean == same and clean != other
    original = deepcopy(clean)
    lab._attack(clean, now, 'trust-laundering')
    assert clean == original


def test_campaign_hold_is_pr_specific():
    from trustnet.campaigns import detect
    clean, now = lab._network(42)
    attacked = lab._attack(clean, now, 'collusive-cluster')
    campaigns = detect(attacked, False)
    affected = attacked.prs[-1]
    unrelated = deepcopy(affected)
    unrelated.id = 'unrelated'
    assert evaluate_pr(attacked, 'viewer', affected, campaigns).in_campaign
    result = evaluate_pr(attacked, 'viewer', unrelated, campaigns)
    assert result.decision == 'PROVISIONAL' and not result.in_campaign


def test_generic_hold_is_not_campaign_false_positive(monkeypatch):
    original = lab._attack

    def attack(*args):
        net = original(*args)
        for handle in net.accounts:
            if handle.startswith('newcomer-'):
                net.projects['viewer'].denounces.append(Denounce(handle, 'spam', 'https://example.test'))
        return net
    monkeypatch.setattr(lab, '_attack', attack)
    for row in lab.run(use_embeddings=False)['scenarios'].values():
        assert row['newcomer_hold_rate'] == 1
        assert row['campaign_false_positive_rate'] == 0


def test_ollama_unreachable_matches_explicit_offline(monkeypatch):
    import requests

    def unavailable(*args, **kwargs):
        raise requests.ConnectionError('offline fixture')
    monkeypatch.setattr('trustnet.similarity.requests.post', unavailable)
    assert lab.run(use_embeddings=True) == lab.run(use_embeddings=False)
