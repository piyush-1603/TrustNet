"""The run console exposes actual repository records and engine results."""
from types import SimpleNamespace

from trustnet.campaigns import detect
from trustnet.lab import run as run_lab
from trustnet.report import render
from trustnet.simulate import generate
from trustnet.trust import evaluate_pr


def test_empty_network_still_renders(tmp_path):
    net = SimpleNamespace(projects={}, accounts={}, prs=[])
    out = tmp_path / 'report.html'
    render(net, [], [], {}, out)
    html = out.read_text()
    assert 'run console' in html
    assert 'No repositories in this snapshot.' in html


def test_report_shows_real_run_pipeline_repositories_and_cases(tmp_path):
    net, _ = generate(seed=42)
    campaigns = detect(net, use_embeddings=False)
    decisions = [evaluate_pr(net, 'proj-01', pr, campaigns) for pr in net.prs]
    lab = run_lab(use_embeddings=False)
    out = tmp_path / 'report.html'
    render(net, decisions, campaigns, lab, out)
    html = out.read_text()
    for topic in ('Repository explorer', 'Campaign findings', 'What the defenses do', 'Load snapshot', 'Find coordination', 'Evaluate PRs'):
        assert topic in html
    assert 'repo-trigger' in html
    assert 'role="listbox"' in html
    assert 'Trust nodes without PRs' in html
    assert 'pr-001' in html
    assert 'Inspect linked PRs and accounts' in html
    assert 'trust 0.80' in html
    assert 'brigade-denounce' in html
    assert 'trusted-source-compromise' in html
    assert 'not proof that an account is fraudulent' in html


def test_report_escapes_input_and_includes_paths(tmp_path):
    net, _ = generate(seed=42)
    pr = next(p for p in net.prs if p.id == 'pr-001')
    decision = evaluate_pr(net, 'proj-01', pr, [])
    decision.author = '<script>alert(1)</script>'
    out = tmp_path / 'report.html'
    render(net, [decision], [], {}, out)
    html = out.read_text()
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;alert(1)&lt;/script&gt;' in html
    assert 'Contributing trust paths' in html
