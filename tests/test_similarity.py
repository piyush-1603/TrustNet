from unittest.mock import Mock

import numpy as np
import pytest
import requests

from trustnet.similarity import similarity_matrices, similarity_matrix


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr('trustnet.similarity.requests.post', Mock(side_effect=requests.ConnectionError()))


def test_tfidf_and_failed_ollama_are_identical():
    texts = ['fix authentication security', 'fix authentication security', 'update documentation']
    fallback, used = similarity_matrix(texts)
    expected, _ = similarity_matrix(texts, False)
    np.testing.assert_allclose(fallback, expected)
    assert not used
    assert fallback[0, 1] == pytest.approx(1)
    assert fallback[0, 2] == 0


def test_real_api_contract_and_elementwise_max(monkeypatch):
    post = Mock(return_value=Mock(json=lambda: {'embeddings': [[1., 0.], [1., 0.]]}))
    monkeypatch.setattr('trustnet.similarity.requests.post', post)
    matrix, used = similarity_matrix(['repair login validation', 'secure user authentication'])
    assert used
    assert matrix[0, 1] == pytest.approx(1)
    post.assert_called_once_with('http://localhost:11434/api/embed',
        json={'model': 'nomic-embed-text', 'input': ['repair login validation', 'secure user authentication']},
        timeout=(2, 30))


@pytest.mark.parametrize('payload', [{}, {'embeddings': [[1, 2]]},
    {'embeddings': [[0, 0], [1, 2]]}, {'embeddings': [[float('nan')], [1]]},
    {'embeddings': [[], []]}, {'embeddings': [[1], [1, 2]]}])
def test_malformed_model_response_falls_back(monkeypatch, payload):
    monkeypatch.setattr('trustnet.similarity.requests.post', Mock(return_value=Mock(json=lambda: payload)))
    matrix, used = similarity_matrix(['same words', 'same words'])
    assert not used
    assert matrix[0, 1] == pytest.approx(1)


def test_http_error_and_timeout_fall_back(monkeypatch):
    for failure in (requests.Timeout(), requests.HTTPError()):
        monkeypatch.setattr('trustnet.similarity.requests.post', Mock(side_effect=failure))
        assert similarity_matrix(['text'])[1] is False


def test_non_success_http_status_is_not_used(monkeypatch):
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError('model not found')
    monkeypatch.setattr('trustnet.similarity.requests.post', Mock(return_value=response))
    assert similarity_matrix(['text'])[1] is False
    response.json.assert_not_called()


def test_empty_and_punctuation_only_inputs():
    assert similarity_matrix([])[0].shape == (0, 0)
    matrix, used = similarity_matrix(['', '!!!'], False)
    assert not used
    assert not matrix.any()
    assert similarity_matrix(['a', 'a'], False)[0][0, 1] == pytest.approx(1)


def test_opt_out_never_calls_http():
    similarity_matrix(['text'], False)
    from trustnet.similarity import requests as client
    client.post.assert_not_called()


def test_non_strings_are_rejected():
    with pytest.raises(TypeError):
        similarity_matrix([None])


def test_embeddings_are_requested_in_batches(monkeypatch):
    sizes = []

    def post(url, json, timeout):
        sizes.append(len(json['input']))
        return Mock(json=lambda: {'embeddings': [[1., 0.]] * len(json['input'])})

    monkeypatch.setattr('trustnet.similarity.requests.post', post)
    keyword, embedding = similarity_matrices([f'text {i}' for i in range(70)])
    assert sizes == [32, 32, 6] and embedding.shape == (70, 70) and keyword.shape == (70, 70)


def test_the_two_scores_are_returned_separately(monkeypatch):
    monkeypatch.setattr('trustnet.similarity.requests.post',
                        Mock(return_value=Mock(json=lambda: {'embeddings': [[1., 0.], [.8, .6]]})))
    keyword, embedding = similarity_matrices(['alpha beta', 'gamma delta'])
    assert keyword[0, 1] == 0 and embedding[0, 1] == pytest.approx(.8)
    assert similarity_matrices(['alpha beta', 'gamma delta'], False)[1] is None
