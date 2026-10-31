"""
tests/test_simulate.py
Tests for trustnet/simulate.py.
No Ollama, no internet, no secrets required.
"""
import json
import tempfile
from pathlib import Path

from trustnet.simulate import generate, write_network


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_tmp(seed=42):
    """Generate and write a network to a temp dir; return (net, labels, path)."""
    net, labels = generate(seed=seed)
    tmp = tempfile.mkdtemp()
    write_network(net, labels, tmp)
    return net, labels, Path(tmp)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_deterministic_same_seed():
    """Same seed must produce identical labels and project keys."""
    _, labels1 = generate(seed=42)
    _, labels2 = generate(seed=42)
    assert labels1 == labels2


def test_different_seeds_differ():
    """Different seeds must produce structurally different networks."""
    net1, labels1 = generate(seed=42)
    net2, labels2 = generate(seed=99)
    # The trust graph edges are sampled, so they differ across seeds
    trusts1 = {
        (pid, t.project)
        for pid, proj in net1.projects.items()
        for t in proj.trusts
    }
    trusts2 = {
        (pid, t.project)
        for pid, proj in net2.projects.items()
        for t in proj.trusts
    }
    assert trusts1 != trusts2, "Trust graphs should differ for different seeds"


def test_write_network_creates_files():
    """write_network must produce the expected folder layout."""
    net, labels, out = _write_tmp()
    assert (out / "accounts.json").exists()
    assert (out / "prs.json").exists()
    assert (out / "labels.json").exists()
    assert (out / "projects").is_dir()
    # At least the honest projects are written
    proj_files = list((out / "projects").glob("proj-*.json"))
    assert len(proj_files) == 30  # default n_projects


def test_deterministic_json_files():
    """Two runs with seed=42 must produce byte-identical JSON files."""
    _, l1, out1 = _write_tmp(seed=42)
    _, l2, out2 = _write_tmp(seed=42)

    for fname in ("accounts.json", "prs.json", "labels.json"):
        assert (out1 / fname).read_text() == (out2 / fname).read_text(), fname

    for f in (out1 / "projects").glob("*.json"):
        twin = out2 / "projects" / f.name
        assert f.read_text() == twin.read_text(), f.name


def test_newcomers_in_labels():
    """15 newcomers must appear in labels and have no vouches in any project."""
    net, labels, _ = _write_tmp()
    assert len(labels["newcomer_handles"]) == 15

    # Collect all vouched handles across all projects
    vouched = set()
    for proj in net.projects.values():
        for v in proj.vouches:
            vouched.add(v.handle)

    for handle in labels["newcomer_handles"]:
        assert handle in net.accounts, f"{handle} missing from accounts"
        assert handle not in vouched, f"{handle} should have no vouches"


def test_campaign_planted():
    """Spam campaign must have exactly 38 PR IDs in labels."""
    _, labels, _ = _write_tmp()
    assert len(labels["campaign_pr_ids"]) == 38


def test_campaign_pr_ids_in_prs_json():
    """All campaign PR IDs must appear in prs.json."""
    _, labels, out = _write_tmp()
    prs = json.loads((out / "prs.json").read_text())
    pr_ids = {p["id"] for p in prs}
    for pr_id in labels["campaign_pr_ids"]:
        assert pr_id in pr_ids, f"Campaign PR {pr_id} missing from prs.json"


def test_campaign_accounts_are_new():
    """
    All spam bot accounts must be < 14 days old at generation time
    (2026-10-31T20:00:00Z).
    """
    from datetime import datetime, timezone
    net, labels, _ = _write_tmp()
    now = datetime(2026, 10, 31, 20, 0, 0, tzinfo=timezone.utc)
    for handle in labels["attack_handles"]:
        if handle.startswith("bot-"):
            acct = net.accounts[handle]
            age_days = (now - acct.created_at).days
            assert age_days < 14, f"{handle} is {age_days} days old, expected < 14"


def test_legit_bump_planted():
    """Legit bulk bump must have exactly 10 PR IDs."""
    _, labels, _ = _write_tmp()
    assert len(labels["legit_bump_pr_ids"]) == 10


def test_legit_bump_author_is_old():
    """The maintainer account for the legit bump must be > 14 days old."""
    from datetime import datetime, timezone
    net, labels, _ = _write_tmp()
    now = datetime(2026, 10, 31, 20, 0, 0, tzinfo=timezone.utc)
    acct = net.accounts["maintainer-dep"]
    age_days = (now - acct.created_at).days
    assert age_days >= 365, f"maintainer-dep is only {age_days} days old"


def test_brigaded_handle_present():
    """The brigaded handle must exist in accounts and have fake denounces."""
    net, labels, _ = _write_tmp()
    handle = labels["brigaded_handle"]
    assert handle in net.accounts

    # Fake brigade projects must denounce the handle
    brigade_projs = [p for pid, p in net.projects.items()
                     if pid.startswith("fake-brigade-")]
    assert len(brigade_projs) == 5
    for proj in brigade_projs:
        denounced = [d.handle for d in proj.denounces]
        assert handle in denounced


def test_sybil_spammer_in_accounts():
    """Sybil spammer handle must exist in accounts."""
    net, labels, _ = _write_tmp()
    assert labels["sybil_spammer_handle"] == "spammer-zed"
    assert "spammer-zed" in net.accounts


def test_sybil_clique_has_no_real_trust():
    """Sybil fake projects must not be trusted by any honest project."""
    net, labels, _ = _write_tmp()
    sybil_ids = {f"fake-sybil-{i:02d}" for i in range(4)}

    for pid, proj in net.projects.items():
        if pid.startswith("fake-"):
            continue  # only check honest projects
        for t in proj.trusts:
            assert t.project not in sybil_ids, (
                f"Honest project {pid} trusts sybil {t.project}"
            )


def test_project_json_schema():
    """Each project JSON must have the required keys."""
    _, _, out = _write_tmp()
    for f in (out / "projects").glob("*.json"):
        data = json.loads(f.read_text())
        assert "id" in data
        assert "name" in data
        assert "trusts" in data
        assert "vouches" in data
        assert "denounces" in data
        # trust entries
        for t in data["trusts"]:
            assert "project" in t and "weight" in t


def test_accounts_json_schema():
    """accounts.json entries must have handle and created_at."""
    _, _, out = _write_tmp()
    accs = json.loads((out / "accounts.json").read_text())
    assert len(accs) > 0
    for a in accs:
        assert "handle" in a
        assert "created_at" in a


def test_prs_json_schema():
    """prs.json entries must have all required fields."""
    _, _, out = _write_tmp()
    prs = json.loads((out / "prs.json").read_text())
    required = {"id", "project", "author", "created_at", "title", "body", "diff_text"}
    for pr in prs:
        assert required <= pr.keys(), f"Missing keys in PR: {required - pr.keys()}"


def test_labels_json_schema():
    """labels.json must contain all six expected keys."""
    _, _, out = _write_tmp()
    labels = json.loads((out / "labels.json").read_text())
    for key in (
        "campaign_pr_ids", "newcomer_handles", "attack_handles",
        "brigaded_handle", "legit_bump_pr_ids", "sybil_spammer_handle",
    ):
        assert key in labels, f"Missing key in labels.json: {key}"


# ---------------------------------------------------------------------------
# Edge Cases
# ---------------------------------------------------------------------------

def test_simulate_zero_projects_raises():
    """Passing n_projects < 1 must raise ValueError."""
    import pytest
    with pytest.raises(ValueError, match="at least 1"):
        generate(n_projects=0)
    with pytest.raises(ValueError, match="at least 1"):
        generate(n_projects=-5)


def test_simulate_minimal_single_project():
    """Boundary test: n_projects=1 must not crash and produce valid network."""
    net, labels = generate(n_projects=1, seed=42)
    assert len(labels["newcomer_handles"]) == 15
    assert len(labels["campaign_pr_ids"]) == 38
    # 1 honest + 5 brigade + 4 sybil = 10 projects
    assert len(net.projects) == 10
    with tempfile.TemporaryDirectory() as tmp:
        write_network(net, labels, Path(tmp) / "nested" / "dir")
        assert (Path(tmp) / "nested" / "dir" / "accounts.json").exists()


def test_trusted_denounce_planted():
    """Trusted denounce planted case must exist in labels and evaluate to HOLD."""
    from trustnet.trust import evaluate_pr
    net, labels, _ = _write_tmp()
    assert "trusted_denounced_handle" in labels
    assert "trusted_denounced_pr_id" in labels
    pr_id = labels["trusted_denounced_pr_id"]
    pr = next(p for p in net.prs if p.id == pr_id)
    dec = evaluate_pr(net, "proj-01", pr, campaigns=[])
    assert dec.decision == "HOLD"
    assert any("denounced by proj-01" in r for r in dec.reasons)


def test_brigaded_author_vouched_by_trusted_project():
    """Brigaded author must be vouched by proj-01 and evaluate to ACCEPT from proj-01."""
    from trustnet.trust import evaluate_pr
    net, labels, _ = _write_tmp()
    handle = labels["brigaded_handle"]
    vouched = [v.handle for v in net.projects["proj-01"].vouches]
    assert handle in vouched
    pr = next((p for p in net.prs if p.author == handle), None)
    if pr:
        dec = evaluate_pr(net, "proj-01", pr, campaigns=[])
        assert dec.decision == "ACCEPT"

