"""Test-only contract substitutes while Person 1's models are unmerged."""
from datetime import datetime, timedelta, timezone
import sys
from types import ModuleType, SimpleNamespace as Record
from unittest.mock import Mock

import numpy as np
import pytest
import requests

from trustnet import campaigns


@pytest.fixture
def contract(monkeypatch):
    # Local to each test: never replace shared production modules on disk.
    module = ModuleType('trustnet.models')
    for name in ('Account', 'Campaign', 'Denounce', 'Network', 'PR', 'Project', 'Trust', 'Vouch'):
        setattr(module, name, Record)
    monkeypatch.setitem(sys.modules, 'trustnet.models', module)
    monkeypatch.setattr('trustnet.similarity.requests.post', Mock(side_effect=requests.ConnectionError()))
    return module


def network(count=20, old=False, span_hours=2):
    now = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
    accounts, prs = {}, []
    for i in range(count):
        author = 'maintainer' if old else f'user-{i}'
        accounts[author] = Record(handle=author, created_at=now - timedelta(days=100 if old else 2))
        prs.append(Record(id=f'pr-{i:02}', project=f'project-{i % 10}', author=author,
            created_at=now + timedelta(hours=span_hours * i / max(1, count - 1)),
            title='Bump dependency version', body='Update dependency to the latest release', diff_text='+ version 2'))
    return Record(accounts=accounts, prs=prs, projects={
        f'project-{i}': Record(vouches=[Record(handle='maintainer')]) for i in range(10)})


def test_planted_campaign_and_evidence(contract):
    found = campaigns.detect(network())
    assert len(found) == 1 and found[0].flagged
    assert found[0].embedding_used is False
    assert found[0].score == pytest.approx(1)
    assert '20 PRs, 10 projects, 2h00m window, 100%' in found[0].evidence[0]
    assert 'policy_hash=' in found[0].evidence[-1]


def test_legitimate_bulk_dependency_bump_is_not_flagged(contract):
    assert campaigns.detect(network(count=10, old=True)) == []


def test_honest_newcomers_with_unrelated_prs_are_not_flagged(contract, monkeypatch):
    net = network()
    monkeypatch.setattr(campaigns, 'similarity_matrix', lambda texts, use: (np.eye(len(texts)), False))
    assert campaigns.detect(net) == []


def test_paraphrased_spam_clusters_with_mocked_embeddings(contract, monkeypatch):
    net = network()
    for i, pr in enumerate(net.prs):
        pr.title, pr.body, pr.diff_text = f'word{i}', '', ''
    assert campaigns.detect(net, False) == []
    monkeypatch.setattr('trustnet.similarity.requests.post', Mock(return_value=Mock(
        json=lambda: {'embeddings': [[1., 0.]] * len(net.prs)})))
    found = campaigns.detect(net)
    assert len(found) == 1 and found[0].flagged and found[0].embedding_used


@pytest.mark.parametrize('case', ['small', 'few_projects', 'late', 'old', 'missing', 'future', 'age_boundary'])
def test_campaign_gates(contract, case):
    net = network()
    if case == 'small':
        net.prs = net.prs[:7]
    elif case == 'few_projects':
        for pr in net.prs:
            pr.project = 'one-project'
    elif case == 'late':
        net = network(span_hours=6.01)
    elif case == 'old':
        net = network(old=True)
    elif case == 'missing':
        net.accounts.clear()
    elif case in ('future', 'age_boundary'):
        for pr in net.prs:
            net.accounts[pr.author].created_at = pr.created_at + timedelta(days=1 if case == 'future' else -14)
    assert campaigns.detect(net, False) == []


def test_window_boundary_and_distinct_authors(contract):
    assert campaigns.detect(network(span_hours=6), False)[0].flagged
    net = network()
    # Repeating one young author does not overwhelm nine distinct old authors.
    for i, pr in enumerate(net.prs):
        if i < 11:
            pr.author = 'user-0'
        else:
            net.accounts[pr.author].created_at -= timedelta(days=100)
    assert campaigns.detect(net, False) == []


def test_shared_policy_controls_detector(contract, monkeypatch):
    loader = ModuleType('trustnet.loaders')
    loader.load_policy = lambda: ({'campaigns': {'min_prs': 21}}, 'unused-hash')
    monkeypatch.setitem(sys.modules, 'trustnet.loaders', loader)
    assert campaigns.detect(network(), False) == []


def test_connected_components_and_score_threshold(contract, monkeypatch):
    net = network(count=8)
    matrix = np.eye(8)
    for i in range(7):
        matrix[i, i + 1] = matrix[i + 1, i] = .85
    monkeypatch.setattr(campaigns, 'similarity_matrix', lambda texts, use: (matrix, False))
    assert len(campaigns.detect(net, False)[0].pr_ids) == 8
    for pr in net.prs:
        pr.project = f'project-{int(pr.id[-2:]) % 5}'
    for pr in net.prs[:2]:
        net.accounts[pr.author].created_at -= timedelta(days=100)
    campaign = campaigns.detect(net, False)[0]
    assert campaign.score == pytest.approx(.535)
    assert not campaign.flagged


def test_no_prs(contract):
    assert campaigns.detect(network(count=0)) == []
