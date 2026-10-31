"""CLI tests for the later commands: advisory, evaluate --advisory, fanout, ablation, path to trust.

No Ollama, internet or secrets needed: every command that can use the model is run with --no-embeddings.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run([sys.executable, "-m", "trustnet", *args], capture_output=True, text=True, cwd=str(ROOT))


@pytest.fixture(scope="module")
def network(tmp_path_factory):
    out = tmp_path_factory.mktemp("net")
    assert run("simulate", "--projects", "30", "--seed", "42", "--out", str(out)).returncode == 0
    return out


def evaluate(network, viewer, pr, *extra):
    result = run("evaluate", "--as", viewer, "--pr", pr, "--network", str(network), "--no-embeddings", "--json", *extra)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_advisory_is_written_and_lists_the_campaign_accounts(network, tmp_path):
    out = tmp_path / "adv.json"
    result = run("advisory", "--as", "proj-01", "--network", str(network), "--out", str(out), "--no-embeddings")
    assert result.returncode == 0, result.stderr
    data = json.loads(out.read_text())
    assert data["format"] == "trustnet-advisory/1" and data["issuer"] == "proj-01"
    assert data["campaigns"] and "bot-00" in data["campaigns"][0]["authors"]


def test_an_advisory_holds_only_where_the_issuer_is_trusted(network, tmp_path):
    out = tmp_path / "adv.json"
    run("advisory", "--as", "proj-01", "--network", str(network), "--out", str(out), "--no-embeddings")
    base = ("--no-local-detection",)
    assert evaluate(network, "proj-02", "pr-151", *base)["decision"] == "PROVISIONAL"
    trusted = evaluate(network, "proj-02", "pr-151", *base, "--advisory", str(out))
    assert trusted["decision"] == "HOLD" and "advisory" in " ".join(trusted["reasons"])
    untrusted = evaluate(network, "proj-03", "pr-151", *base, "--advisory", str(out))
    assert untrusted["decision"] == "PROVISIONAL"
    assert any("advisory from proj-01" in line for line in untrusted["ignored"])


def test_a_broken_advisory_file_is_rejected_with_a_message(network, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{}")
    result = run("evaluate", "--as", "proj-02", "--pr", "pr-151", "--network", str(network), "--no-embeddings",
                 "--advisory", str(bad))
    assert result.returncode == 1 and "not a trustnet-advisory/1 file" in result.stderr


def test_a_newcomer_is_told_how_to_earn_trust(network):
    decision = evaluate(network, "proj-01", "pr-203")
    assert decision["decision"] == "PROVISIONAL"
    assert decision["next_steps"] and "to reach ACCEPT" in decision["next_steps"][0]


def test_known_demo_pr_decisions(network):
    assert evaluate(network, "proj-01", "pr-002")["decision"] == "ACCEPT"    # brigade ignored
    assert evaluate(network, "proj-01", "pr-202")["decision"] == "HOLD"      # trusted denounce
    assert evaluate(network, "proj-01", "pr-189")["decision"] == "ACCEPT"    # legitimate bulk bump
    assert evaluate(network, "proj-01", "pr-001")["decision"] == "ACCEPT"
    assert evaluate(network, "proj-05", "pr-001")["decision"] == "PROVISIONAL"   # same PR, other viewpoint


def test_fanout_command_separates_the_three_people():
    result = run("fanout", "--json")
    assert result.returncode == 0, result.stderr
    people = {p["handle"]: p for p in json.loads(result.stdout)["people"]}
    assert (people["fresh-ai-user"]["behavior_flag"], people["fresh-ai-user"]["decision"]) == (True, "HOLD")
    assert (people["busy-maintainer"]["behavior_flag"], people["busy-maintainer"]["decision"]) == (False, "ACCEPT")
    assert (people["eager-newcomer"]["behavior_flag"], people["eager-newcomer"]["decision"]) == (True, "ACCEPT")


def test_ablation_command_never_flags_the_reworded_campaign_without_the_model():
    result = run("ablation", "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["model_off"]["flagged"] is False
    if data["model_available"]:                       # only when Ollama happens to be running
        assert data["model_on"]["flagged"] and data["honest_flagged_with_model"] == []
    else:
        assert data["model_on"] is None
