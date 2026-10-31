from unittest.mock import Mock

import pytest
import requests

from trustnet import ablation
from trustnet.campaigns import pr_text


def fake_model(spam_texts):
    """A stand-in model that gives every reworded spam text the same direction and each other text its own."""
    seen = {}

    def post(url, json, timeout):
        vectors = []
        for text in json['input']:
            vector = [0.0] * 64
            vector[0 if text in spam_texts else 1 + seen.setdefault(text, len(seen))] = 1.0
            vectors.append(vector)
        return Mock(json=lambda: {'embeddings': vectors})
    return post


def test_keyword_matching_cannot_link_the_reworded_campaign(monkeypatch):
    monkeypatch.setattr('trustnet.similarity.requests.post', Mock(side_effect=requests.ConnectionError()))
    result = ablation.run()
    assert result['model_off'] == {'flagged': False, 'pr_ids': [], 'embedding_used': False}
    assert result['model_available'] is False and result['model_on'] is None  # no model result is invented


def test_a_model_that_sees_the_shared_meaning_finds_all_twelve_and_no_ordinary_pr(monkeypatch):
    net = ablation.build_network()
    spam_texts = {pr_text(pr) for pr in net.prs if pr.id.startswith('spam-')}
    monkeypatch.setattr('trustnet.similarity.requests.post', fake_model(spam_texts))
    result = ablation.run()
    assert result['model_off']['flagged'] is False
    assert result['model_on']['flagged'] and result['model_on']['embedding_used']
    assert len(result['spam_ids_found_with_model']) == 12 and result['honest_flagged_with_model'] == []


def test_the_background_prs_come_from_old_accounts_and_the_spam_from_new_ones():
    net = ablation.build_network()
    spam = [a for h, a in net.accounts.items() if h.startswith('fresh-')]
    honest = [a for h, a in net.accounts.items() if h.startswith('regular-')]
    assert len(spam) == 12 and len(honest) == len(ablation.HONEST)
    assert all(a.created_at > min(h.created_at for h in honest) for a in spam)


def ollama_has_the_model():
    try:
        tags = requests.get('http://localhost:11434/api/tags', timeout=2).json()
        return any(m['name'].startswith('nomic-embed-text') for m in tags.get('models', []))
    except Exception:
        return False


@pytest.mark.skipif(not ollama_has_the_model(), reason='needs Ollama running with nomic-embed-text')
def test_with_the_real_model_the_campaign_is_found_and_ordinary_prs_are_not():
    result = ablation.run()
    assert result['model_off']['flagged'] is False
    assert result['model_available'] and result['model_on']['flagged']
    assert len(result['spam_ids_found_with_model']) >= 8 and result['honest_flagged_with_model'] == []
