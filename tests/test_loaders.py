import json

import pytest

from trustnet.loaders import POLICY_PATH, load_network, load_policy


def write_network(root, projects=None, accounts=None, prs=None):
    (root / "projects").mkdir(parents=True, exist_ok=True)
    projects = projects if projects is not None else [{
        "id": "proj-a", "name": "A",
        "trusts": [{"project": "proj-b", "weight": 0.9}],
        "vouches": [{"handle": "alice", "date": "2026-09-01T00:00:00Z", "evidence_url": None}],
        "denounces": [{"handle": "bot", "reason_code": "spam", "evidence_url": "https://example.test/e",
                       "date": "2026-10-30T00:00:00Z", "expires": None}],
    }, {"id": "proj-b", "name": "B"}]
    for project in projects:
        (root / "projects" / f"{project['id']}.json").write_text(json.dumps(project))
    (root / "accounts.json").write_text(json.dumps(accounts if accounts is not None else
        [{"handle": "alice", "created_at": "2019-03-02T00:00:00Z"}]))
    (root / "prs.json").write_text(json.dumps(prs if prs is not None else [{
        "id": "pr-1", "project": "proj-a", "author": "alice", "created_at": "2026-10-31T10:00:00Z",
        "title": "Fix typo", "body": "docs", "diff_text": "+x"}]))
    return root


def test_loads_a_valid_network(tmp_path):
    net = load_network(write_network(tmp_path))
    assert sorted(net.projects) == ["proj-a", "proj-b"]
    a = net.projects["proj-a"]
    assert a.trusts[0].project == "proj-b" and a.trusts[0].weight == 0.9
    assert a.vouches[0].handle == "alice" and a.vouches[0].evidence_url is None
    assert a.denounces[0].reason_code == "spam" and a.denounces[0].expires is None
    assert net.projects["proj-b"].name == "B" and net.projects["proj-b"].vouches == []
    assert net.accounts["alice"].created_at == "2019-03-02T00:00:00Z"
    assert net.prs[0].id == "pr-1" and net.prs[0].title == "Fix typo"


def test_ignores_labels_json(tmp_path):
    write_network(tmp_path)
    (tmp_path / "labels.json").write_text("this is not even json")
    assert load_network(tmp_path).prs


def test_rejects_a_denounce_without_reason_code(tmp_path):
    bad = [{"id": "proj-a", "name": "A", "denounces": [{"handle": "bot", "evidence_url": "https://example.test"}]}]
    with pytest.raises(ValueError, match=r"proj-a\.json: denounces\[0\]: 'reason_code'"):
        load_network(write_network(tmp_path, projects=bad))


@pytest.mark.parametrize("weight", [1.5, -0.1, "high", True, None])
def test_rejects_bad_trust_weights(tmp_path, weight):
    bad = [{"id": "proj-a", "name": "A", "trusts": [{"project": "proj-b", "weight": weight}]}]
    with pytest.raises(ValueError, match="weight"):
        load_network(write_network(tmp_path, projects=bad))


def test_rejects_file_name_that_differs_from_id(tmp_path):
    root = write_network(tmp_path)
    (root / "projects" / "proj-a.json").rename(root / "projects" / "renamed.json")
    with pytest.raises(ValueError, match="must match the file name"):
        load_network(root)


def test_rejects_bad_timestamps(tmp_path):
    bad_vouch = [{"id": "proj-a", "name": "A", "vouches": [{"handle": "alice", "date": "last week"}]}]
    with pytest.raises(ValueError, match=r"vouches\[0\]: 'date'"):
        load_network(write_network(tmp_path / "one", projects=bad_vouch))
    with pytest.raises(ValueError, match="'created_at' is required"):
        load_network(write_network(tmp_path / "two", accounts=[{"handle": "alice"}]))


def test_rejects_duplicates(tmp_path):
    accounts = [{"handle": "alice", "created_at": "2019-01-01T00:00:00Z"}] * 2
    with pytest.raises(ValueError, match="duplicate handle"):
        load_network(write_network(tmp_path / "one", accounts=accounts))
    pr = {"id": "pr-1", "project": "proj-a", "author": "alice", "created_at": "2026-10-31T10:00:00Z"}
    with pytest.raises(ValueError, match="duplicate PR id"):
        load_network(write_network(tmp_path / "two", prs=[pr, pr]))


def test_rejects_missing_or_broken_files(tmp_path):
    with pytest.raises(ValueError, match="no projects"):
        load_network(tmp_path)
    root = write_network(tmp_path / "net")
    (root / "prs.json").write_text("{")
    with pytest.raises(ValueError, match="prs.json: cannot read"):
        load_network(root)


def test_policy_loads_with_a_stable_hash():
    policy, digest = load_policy()
    assert policy["trust"]["decay"] == 0.6 and policy["campaigns"]["min_prs"] == 8
    assert load_policy() == (policy, digest) and len(digest) == 12


def test_policy_hash_changes_when_a_value_changes(tmp_path):
    policy, digest = load_policy()
    policy["trust"]["decay"] = 0.5
    changed = tmp_path / "policy.json"
    changed.write_text(json.dumps(policy))
    assert load_policy(changed)[1] != digest


def test_policy_rejects_missing_or_out_of_range_values(tmp_path):
    policy = json.loads(POLICY_PATH.read_text())
    for edit, message in ((lambda p: p["trust"].pop("decay"), "trust.decay"),
                          (lambda p: p["trust"].update(decay=0), "out of range"),
                          (lambda p: p["trust"].update(max_hops=2.5), "whole number"),
                          (lambda p: p.pop("decision"), "missing section 'decision'")):
        broken = json.loads(json.dumps(policy))
        edit(broken)
        path = tmp_path / "policy.json"
        path.write_text(json.dumps(broken))
        with pytest.raises(ValueError, match=message):
            load_policy(path)
