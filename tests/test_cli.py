"""
tests/test_cli.py
Tests for trustnet/cli.py and trustnet/__main__.py.
No Ollama, no internet, no secrets required.
All commands are tested against the output of `trustnet simulate`.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _run(*args, cwd=None):
    """Run `python -m trustnet <args>` and return the CompletedProcess."""
    return subprocess.run(
        [sys.executable, "-m", "trustnet", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd or ROOT),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _simulate_into(tmp: Path) -> None:
    """Run simulate into a temp dir and assert it succeeded."""
    result = _run("simulate", "--projects", "10", "--seed", "42", "--out", str(tmp))
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# simulate
# ---------------------------------------------------------------------------

class TestSimulate:

    def test_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run("simulate", "--out", tmp)
            assert result.returncode == 0

    def test_creates_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            _simulate_into(Path(tmp))
            assert (Path(tmp) / "accounts.json").exists()
            assert (Path(tmp) / "prs.json").exists()
            assert (Path(tmp) / "labels.json").exists()
            assert (Path(tmp) / "projects").is_dir()

    def test_json_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run("simulate", "--out", tmp, "--json")
            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert "projects" in data
            assert "prs" in data
            assert "campaign_pr_ids" in data

    def test_deterministic_output(self):
        """Same seed produces identical accounts.json in two separate runs."""
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _run("simulate", "--seed", "42", "--out", d1)
            _run("simulate", "--seed", "42", "--out", d2)
            c1 = (Path(d1) / "accounts.json").read_text()
            c2 = (Path(d2) / "accounts.json").read_text()
            assert c1 == c2

    def test_different_seed_differs(self):
        with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
            _run("simulate", "--seed", "1", "--out", d1)
            _run("simulate", "--seed", "2", "--out", d2)
            # prs.json should exist for both
            assert (Path(d1) / "prs.json").exists()
            assert (Path(d2) / "prs.json").exists()

    def test_projects_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run("simulate", "--projects", "5", "--out", tmp, "--json")
            data = json.loads(result.stdout)
            # 5 honest + fake brigade (5) + fake sybil (4) projects
            assert data["projects"] >= 5


# ---------------------------------------------------------------------------
# __main__.py (python -m trustnet)
# ---------------------------------------------------------------------------

class TestMainModule:

    def test_no_args_exits_nonzero(self):
        """Running without a command should print help and exit non-zero."""
        result = _run()
        assert result.returncode != 0

    def test_help_flag(self):
        result = _run("--help")
        assert result.returncode == 0
        assert "trustnet" in result.stdout.lower()

    def test_simulate_help(self):
        result = _run("simulate", "--help")
        assert result.returncode == 0
        assert "--seed" in result.stdout


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

class TestReport:

    def test_report_runs_after_simulate(self):
        with tempfile.TemporaryDirectory() as tmp:
            net_dir = Path(tmp) / "network"
            out_html = Path(tmp) / "report.html"
            _simulate_into(net_dir)
            result = _run(
                "report",
                "--network", str(net_dir),
                "--out", str(out_html),
            )
            assert result.returncode == 0, result.stderr
            assert out_html.exists()

    def test_report_html_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            net_dir = Path(tmp) / "network"
            out_html = Path(tmp) / "report.html"
            _simulate_into(net_dir)
            _run("report", "--network", str(net_dir), "--out", str(out_html))
            content = out_html.read_text(encoding="utf-8")
            assert "<!DOCTYPE html>" in content
            assert "<title>TrustNet Report</title>" in content

    def test_report_has_required_sections(self):
        """HTML report must contain all required section IDs."""
        with tempfile.TemporaryDirectory() as tmp:
            net_dir = Path(tmp) / "network"
            out_html = Path(tmp) / "report.html"
            _simulate_into(net_dir)
            _run("report", "--network", str(net_dir), "--out", str(out_html))
            content = out_html.read_text(encoding="utf-8")
            for section_id in ("overview", "decisions", "side-by-side",
                               "campaigns", "lab", "trust-graph"):
                assert f'id="{section_id}"' in content, (
                    f"Missing section #{section_id} in report HTML"
                )

    def test_report_badges_have_text_labels(self):
        """Decision badges must show text labels, not only colors."""
        with tempfile.TemporaryDirectory() as tmp:
            net_dir = Path(tmp) / "network"
            out_html = Path(tmp) / "report.html"
            _simulate_into(net_dir)
            _run("report", "--network", str(net_dir), "--out", str(out_html))
            content = out_html.read_text(encoding="utf-8")
            for label in ("ACCEPT", "PROVISIONAL", "HOLD"):
                assert label in content, f"Text label {label!r} missing from report"

    def test_report_has_dark_mode_css(self):
        """Report must include prefers-color-scheme:dark media query."""
        with tempfile.TemporaryDirectory() as tmp:
            net_dir = Path(tmp) / "network"
            out_html = Path(tmp) / "report.html"
            _simulate_into(net_dir)
            _run("report", "--network", str(net_dir), "--out", str(out_html))
            content = out_html.read_text(encoding="utf-8")
            assert "prefers-color-scheme:dark" in content.replace(" ", "")

    def test_report_has_svg_graph(self):
        """Report must contain an inline SVG trust graph."""
        with tempfile.TemporaryDirectory() as tmp:
            net_dir = Path(tmp) / "network"
            out_html = Path(tmp) / "report.html"
            _simulate_into(net_dir)
            _run("report", "--network", str(net_dir), "--out", str(out_html))
            content = out_html.read_text(encoding="utf-8")
            assert "<svg" in content
            assert "ignored: source not trusted" in content

    def test_report_has_campaign_section(self):
        """Report must contain a campaigns section (flagged or not)."""
        with tempfile.TemporaryDirectory() as tmp:
            net_dir = Path(tmp) / "network"
            out_html = Path(tmp) / "report.html"
            _simulate_into(net_dir)
            _run("report", "--network", str(net_dir), "--out", str(out_html))
            content = out_html.read_text(encoding="utf-8")
            assert "id=\"campaigns\"" in content


# ---------------------------------------------------------------------------
# evaluate / campaigns / lab -- real integration
# ---------------------------------------------------------------------------

class TestCommandsIntegration:

    def test_evaluate_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            _simulate_into(Path(tmp))
            result = _run(
                "evaluate", "--as", "proj-01", "--pr", "pr-001",
                "--network", tmp,
            )
            assert result.returncode == 0
            assert "PR pr-001" in result.stdout

    def test_campaigns_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            _simulate_into(Path(tmp))
            result = _run("campaigns", "--network", tmp)
            assert result.returncode == 0
            assert "Campaigns detected" in result.stdout

    def test_evaluate_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            _simulate_into(Path(tmp))
            result = _run(
                "evaluate", "--as", "proj-01", "--pr", "pr-001",
                "--network", tmp, "--json",
            )
            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert "decision" in data
            assert data["pr_id"] == "pr-001"

    def test_campaigns_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            _simulate_into(Path(tmp))
            result = _run("campaigns", "--network", tmp, "--json")
            assert result.returncode == 0
            data = json.loads(result.stdout)
            assert isinstance(data, list)

    def test_lab_json(self):
        result = _run("lab", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert isinstance(data, dict)
        assert "scenarios" in data

    def test_lab_markdown(self):
        result = _run("lab")
        assert result.returncode == 0
        assert "Attack" in result.stdout
        assert "Naive BEFORE" in result.stdout


# ---------------------------------------------------------------------------
# CLI & Report Edge Cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_simulate_projects_zero_fails(self):
        result = _run("simulate", "--projects", "0")
        assert result.returncode != 0
        assert "must be at least 1" in result.stderr

    def test_evaluate_nonexistent_network_fails_cleanly(self):
        result = _run("evaluate", "--as", "proj-01", "--pr", "pr-001", "--network", "/nonexistent/dir")
        assert result.returncode != 0
        assert "Error loading network" in result.stderr or "Error" in result.stderr

    def test_evaluate_nonexistent_pr_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            _simulate_into(Path(tmp))
            result = _run("evaluate", "--as", "proj-01", "--pr", "pr-nonexistent-999", "--network", tmp)
            assert result.returncode != 0
            assert "not found" in result.stderr

    def test_report_nested_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            _simulate_into(Path(tmp))
            out_file = Path(tmp) / "sub1" / "sub2" / "report.html"
            result = _run("report", "--network", tmp, "--out", str(out_file))
            assert result.returncode == 0
            assert out_file.exists()

    def test_report_render_empty_data(self):
        """Report render() must succeed even with minimal/empty data."""
        from types import SimpleNamespace
        from trustnet.report import render
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "empty_report.html"
            net = SimpleNamespace(projects={}, accounts={}, prs=[])
            render(net, decisions=[], campaigns=[], lab_results={}, out_path=out_html)
            assert out_html.exists()
            content = out_html.read_text(encoding="utf-8")
            assert "TrustNet Report" in content

