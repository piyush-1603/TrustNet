"""
trustnet/report.py
==================
Renders a self-contained HTML report for TrustNet results.

Public API (do not rename -- contract in docs/PLAN.md):
    render(net, decisions, campaigns, lab_results, out_path) -> None

The function works with real Decision/Campaign objects (Person 1/2 types) OR
with duck-typed SimpleNamespace objects produced by cli._mock_* helpers.
All attributes are accessed with getattr() so missing fields degrade gracefully.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from types import SimpleNamespace


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render(net, decisions, campaigns, lab_results, out_path) -> None:
    """
    Write a self-contained HTML report to out_path.

    Parameters
    ----------
    net : Network (or SimpleNamespace)
    decisions : list[Decision or SimpleNamespace]
    campaigns : list[Campaign or SimpleNamespace]
    lab_results : dict  (scenario -> {"naive": float, "defended": float, ...})
    out_path : str or Path
    """
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    sections = "\n".join([
        _section_overview(net, decisions, campaigns),
        _section_decisions(decisions),
        _section_side_by_side(net, decisions),
        _section_campaigns(campaigns),
        _section_lab(lab_results),
        _section_trust_graph(net),
    ])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="TrustNet decentralised trust evaluation report">
  <title>TrustNet Report</title>
  <style>
{_CSS}
  </style>
</head>
<body>
<header class="site-header">
  <div class="header-inner">
    <span class="logo">&#x1F6E1; TrustNet</span>
    <span class="subtitle">Decentralised Trust Report &middot; {escape(now_str)}</span>
  </div>
</header>
<main>
{sections}
</main>
<footer class="site-footer">
  <p>TrustNet &middot; Team Sophons &middot; Hacktoberfest 2026 Hack Day Sonipat &middot; Problem 7</p>
</footer>
</body>
</html>"""

    Path(out_path).write_text(html, encoding="utf-8")


# ---------------------------------------------------------------------------
# CSS (light + dark, phone-width, contrast >= 4.5:1)
# ---------------------------------------------------------------------------
_CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

:root{
  --bg:#f0f4ff;--surface:#fff;--card:#fff;--card-hover:#f5f8ff;
  --border:#d8e0f0;--text:#0f172a;--text-muted:#5a6e8a;
  --accent:#4f46e5;--accent2:#818cf8;
  --accept-bg:#dcfce7;--accept-text:#15803d;--accept-bd:#86efac;
  --prov-bg:#fef9c3;--prov-text:#854d0e;--prov-bd:#fde047;
  --hold-bg:#fee2e2;--hold-text:#b91c1c;--hold-bd:#fca5a5;
  --node-f:#dbeafe;--node-s:#3b82f6;--node-t:#1e40af;
  --edge:#3b82f6;--edge-dashed:#ef4444;
  --fake-f:#fef2f2;--fake-s:#ef4444;--fake-t:#b91c1c;
  --shadow:0 1px 4px rgba(0,0,0,.08),0 2px 10px rgba(0,0,0,.06);
  --shadow-h:0 4px 16px rgba(0,0,0,.12);
  --r:12px;
}
@media(prefers-color-scheme:dark){
  :root{
    --bg:#080e1f;--surface:#0f1729;--card:#141f35;--card-hover:#1a2844;
    --border:#1e2d4a;--text:#e2e8f0;--text-muted:#94a3b8;
    --accent:#818cf8;--accent2:#a5b4fc;
    --accept-bg:#052e16;--accept-text:#86efac;--accept-bd:#16a34a;
    --prov-bg:#431407;--prov-text:#fcd34d;--prov-bd:#d97706;
    --hold-bg:#450a0a;--hold-text:#fca5a5;--hold-bd:#dc2626;
    --node-f:#0f2144;--node-s:#60a5fa;--node-t:#bfdbfe;
    --edge:#60a5fa;--edge-dashed:#f87171;
    --fake-f:#300a0a;--fake-s:#f87171;--fake-t:#fca5a5;
    --shadow:0 1px 4px rgba(0,0,0,.4),0 2px 10px rgba(0,0,0,.3);
    --shadow-h:0 4px 20px rgba(0,0,0,.5);
  }
}

body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
  background:var(--bg);color:var(--text);line-height:1.6;font-size:16px}

.site-header{background:var(--surface);border-bottom:1px solid var(--border);
  padding:1rem 1.5rem;position:sticky;top:0;z-index:100}
.header-inner{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:.5rem}
.logo{font-size:1.3rem;font-weight:800;color:var(--accent);letter-spacing:-.02em}
.subtitle{font-size:.8rem;color:var(--text-muted)}

main{max-width:1100px;margin:0 auto;padding:2rem 1rem}
section{margin-bottom:3rem}
h2{font-size:1.15rem;font-weight:700;color:var(--text);display:inline-block;
  border-bottom:3px solid var(--accent);padding-bottom:.3rem;margin-bottom:1rem}
.section-note{font-size:.8rem;color:var(--text-muted);margin-bottom:.75rem}

/* stat bar */
.stat-bar{display:flex;gap:.75rem;flex-wrap:wrap;margin-top:1rem}
.stat-card{background:var(--card);border:1px solid var(--border);border-radius:var(--r);
  padding:.85rem 1.25rem;min-width:110px;text-align:center;box-shadow:var(--shadow);flex:1}
.stat-card .num{font-size:1.9rem;font-weight:800;color:var(--accent);line-height:1}
.stat-card .lbl{font-size:.7rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.06em;margin-top:.2rem}

/* badge */
.badge{display:inline-block;padding:.2rem .65rem;border-radius:999px;
  font-size:.72rem;font-weight:800;letter-spacing:.05em;text-transform:uppercase;white-space:nowrap;border-width:1px;border-style:solid}
.badge-accept{background:var(--accept-bg);color:var(--accept-text);border-color:var(--accept-bd)}
.badge-provisional{background:var(--prov-bg);color:var(--prov-text);border-color:var(--prov-bd)}
.badge-hold{background:var(--hold-bg);color:var(--hold-text);border-color:var(--hold-bd)}

/* decision grid */
.decision-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:1rem;margin-top:1rem}
.dc{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:1.1rem;
  box-shadow:var(--shadow);transition:box-shadow .2s,transform .2s}
.dc:hover{box-shadow:var(--shadow-h);transform:translateY(-2px)}
.dc-header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:.65rem}
.pr-id{font-family:ui-monospace,monospace;font-size:.82rem;font-weight:700;color:var(--text)}
.pr-meta{font-size:.75rem;color:var(--text-muted);margin-top:.15rem}
.metrics{display:flex;gap:1.25rem;margin:.65rem 0;flex-wrap:wrap}
.metric .ml{font-size:.68rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:.05em}
.metric .mv{font-size:1rem;font-weight:700;color:var(--text)}
.tag-list{display:flex;flex-wrap:wrap;gap:.3rem;margin-top:.5rem}
.tag{background:var(--surface);border:1px solid var(--border);border-radius:6px;
  padding:.12rem .45rem;font-size:.7rem;color:var(--text-muted);font-family:ui-monospace,monospace}
.tag-ign{background:var(--hold-bg);border-color:var(--hold-bd);color:var(--hold-text)}
.campaign-flag{font-size:.72rem;font-weight:700;color:var(--hold-text);
  background:var(--hold-bg);border:1px solid var(--hold-bd);border-radius:6px;
  padding:.15rem .5rem;display:inline-block;margin-top:.4rem}
.more-note{font-size:.8rem;color:var(--text-muted);text-align:center;margin-top:1rem;padding:.5rem;
  border:1px dashed var(--border);border-radius:var(--r)}

/* side by side */
.sbs-grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:1rem}
.sbs-card{background:var(--card);border:1px solid var(--border);border-radius:var(--r);
  padding:1.1rem;box-shadow:var(--shadow)}
.sbs-viewer{font-size:.75rem;color:var(--text-muted);margin-bottom:.25rem}
.sbs-proj{font-family:ui-monospace,monospace;font-size:.88rem;font-weight:700;margin-bottom:.65rem}

/* campaign card */
.campaign-card{background:var(--card);border:1px solid var(--hold-bd);border-left:4px solid var(--hold-text);
  border-radius:var(--r);padding:1.1rem;margin-top:1rem;box-shadow:var(--shadow)}
.cc-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:.65rem}
.cc-header h3{font-size:.95rem;font-weight:700}
.score-pill{background:var(--hold-bg);color:var(--hold-text);border:1px solid var(--hold-bd);
  border-radius:999px;padding:.15rem .6rem;font-size:.78rem;font-weight:700}
.ev-list{list-style:none;margin-top:.5rem}
.ev-list li{font-size:.82rem;color:var(--text-muted);padding:.18rem 0 .18rem 1.3rem;position:relative}
.ev-list li::before{content:"⚡";position:absolute;left:0;font-size:.7rem}
.cc-counts{display:flex;gap:1.5rem;margin-top:.75rem;flex-wrap:wrap}
.cc-count .cc-num{font-size:1.3rem;font-weight:700;color:var(--hold-text)}
.cc-count .cc-lbl{font-size:.7rem;color:var(--text-muted);text-transform:uppercase}
.no-campaigns{font-size:.9rem;color:var(--text-muted);padding:1rem;
  border:1px dashed var(--border);border-radius:var(--r);text-align:center;margin-top:1rem}

/* lab table */
.lab-wrap{overflow-x:auto;margin-top:1rem}
.lab-table{width:100%;border-collapse:collapse;font-size:.88rem}
.lab-table th,.lab-table td{text-align:left;padding:.65rem 1rem;border-bottom:1px solid var(--border)}
.lab-table th{background:var(--surface);color:var(--text-muted);font-size:.73rem;
  text-transform:uppercase;letter-spacing:.05em;font-weight:600}
.lab-table tr:hover td{background:var(--card-hover)}
.better{color:var(--accept-text);font-weight:700}
.no-lab{font-size:.9rem;color:var(--text-muted);padding:1rem;
  border:1px dashed var(--border);border-radius:var(--r);text-align:center;margin-top:1rem}

/* trust graph */
.graph-wrap{background:var(--card);border:1px solid var(--border);border-radius:var(--r);
  padding:1rem;margin-top:1rem;overflow-x:auto}
.graph-wrap svg{display:block;margin:auto;max-width:100%;height:auto}

/* graph SVG classes (CSS vars work in inline SVG) */
.gn{fill:var(--node-f);stroke:var(--node-s);stroke-width:1.5}
.gn-fake{fill:var(--fake-f);stroke:var(--fake-s);stroke-width:1.5;stroke-dasharray:4 3}
.gn-victim{fill:var(--accept-bg);stroke:var(--accept-bd);stroke-width:2}
.ge{stroke:var(--edge);fill:none;stroke-width:1;stroke-opacity:.5}
.ge-ignored{stroke:var(--edge-dashed);fill:none;stroke-width:1.5;stroke-dasharray:5 4}
.gt{fill:var(--node-t);font-size:8px;text-anchor:middle;dominant-baseline:central;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;font-weight:600}
.gt-fake{fill:var(--fake-t);font-size:8px;text-anchor:middle;dominant-baseline:central;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif}
.ge-label{fill:var(--edge-dashed);font-size:8px;text-anchor:middle;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif}
.graph-legend{font-size:.78rem;color:var(--text-muted);margin-top:.5rem;display:flex;gap:1.5rem;flex-wrap:wrap;justify-content:center}
.legend-item{display:flex;align-items:center;gap:.35rem}
.legend-line{width:24px;height:2px;display:inline-block}
.legend-solid{background:var(--edge)}
.legend-dashed{background:transparent;border-top:2px dashed var(--edge-dashed)}

/* footer */
.site-footer{text-align:center;padding:2rem 1rem;color:var(--text-muted);
  font-size:.8rem;border-top:1px solid var(--border);margin-top:3rem}

/* responsive */
@media(max-width:640px){
  main{padding:1rem .75rem}
  .stat-bar{gap:.5rem}
  .stat-card{min-width:80px;padding:.65rem .9rem}
  .stat-card .num{font-size:1.4rem}
  .decision-grid{grid-template-columns:1fr}
  .sbs-grid{grid-template-columns:1fr}
  .metrics{gap:.75rem}
  h2{font-size:1rem}
}
"""


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _g(obj, attr: str, default=None):
    """getattr with default -- lets us handle both real models and SimpleNamespace."""
    return getattr(obj, attr, default)


def _badge(decision: str) -> str:
    cls = {"ACCEPT": "badge-accept", "PROVISIONAL": "badge-provisional",
           "HOLD": "badge-hold"}.get(decision, "badge-provisional")
    return f'<span class="badge {cls}">{escape(decision)}</span>'


def _fmt(v) -> str:
    """Format a float to 2 dp, or return the value as-is if not numeric."""
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return str(v)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _section_overview(net, decisions: list, campaigns: list) -> str:
    total_prs = len(decisions)
    n_accept = sum(1 for d in decisions if _g(d, "decision") == "ACCEPT")
    n_prov   = sum(1 for d in decisions if _g(d, "decision") == "PROVISIONAL")
    n_hold   = sum(1 for d in decisions if _g(d, "decision") == "HOLD")
    n_camp   = sum(1 for c in campaigns if _g(c, "flagged", False))

    return f"""<section id="overview">
  <h2>Overview</h2>
  <div class="stat-bar">
    <div class="stat-card"><div class="num">{len(net.projects)}</div><div class="lbl">Projects</div></div>
    <div class="stat-card"><div class="num">{len(net.accounts)}</div><div class="lbl">Accounts</div></div>
    <div class="stat-card"><div class="num">{total_prs}</div><div class="lbl">PRs evaluated</div></div>
    <div class="stat-card"><div class="num" style="color:var(--accept-text)">{n_accept}</div><div class="lbl">Accept</div></div>
    <div class="stat-card"><div class="num" style="color:var(--prov-text)">{n_prov}</div><div class="lbl">Provisional</div></div>
    <div class="stat-card"><div class="num" style="color:var(--hold-text)">{n_hold}</div><div class="lbl">Hold</div></div>
    <div class="stat-card"><div class="num" style="color:var(--hold-text)">{n_camp}</div><div class="lbl">Campaigns flagged</div></div>
  </div>
</section>"""


def _decision_card(d) -> str:
    pr_id    = escape(_g(d, "pr_id", "?"))
    author   = escape(_g(d, "author", "?"))
    viewer   = escape(_g(d, "viewer", "?"))
    decision = _g(d, "decision", "PROVISIONAL")
    belief   = _fmt(_g(d, "belief", 0))
    disbelief = _fmt(_g(d, "disbelief", 0))
    uncert   = _fmt(_g(d, "uncertainty", 1))
    reasons  = _g(d, "reasons", []) or []
    ignored  = _g(d, "ignored", []) or []
    in_camp  = _g(d, "in_campaign", False)

    reasons_html = ""
    if reasons:
        items = "".join(f'<span class="tag">{escape(r)}</span>' for r in reasons)
        reasons_html = f'<div class="tag-list">{items}</div>'

    ignored_html = ""
    if ignored:
        items = "".join(f'<span class="tag tag-ign">{escape(i)}</span>' for i in ignored)
        ignored_html = f'<div class="tag-list">{items}</div>'

    camp_flag = '<div class="campaign-flag">&#x26A0; Campaign member</div>' if in_camp else ""

    return f"""<div class="dc">
  <div class="dc-header">
    <div>
      <div class="pr-id">{pr_id}</div>
      <div class="pr-meta">Author: <strong>{author}</strong> &middot; Viewer: {viewer}</div>
    </div>
    {_badge(decision)}
  </div>
  <div class="metrics">
    <div class="metric"><div class="ml">Belief</div><div class="mv">{belief}</div></div>
    <div class="metric"><div class="ml">Disbelief</div><div class="mv">{disbelief}</div></div>
    <div class="metric"><div class="ml">Uncertainty</div><div class="mv">{uncert}</div></div>
  </div>
  {reasons_html}
  {ignored_html}
  {camp_flag}
</div>"""


def _section_decisions(decisions: list) -> str:
    if not decisions:
        return """<section id="decisions">
  <h2>Decisions</h2>
  <p class="section-note">No decisions available. Run <code>trustnet evaluate</code> first.</p>
</section>"""

    # Show a curated subset: all HOLD (up to 8), then PROVISIONAL (up to 6), then ACCEPT (up to 6)
    holds = [d for d in decisions if _g(d, "decision") == "HOLD"][:8]
    provs  = [d for d in decisions if _g(d, "decision") == "PROVISIONAL"][:6]
    accepts = [d for d in decisions if _g(d, "decision") == "ACCEPT"][:6]
    shown = holds + provs + accepts
    total = len(decisions)
    more_note = (f'<div class="more-note">Showing {len(shown)} of {total} decisions '
                 f'(sorted: HOLD first, then PROVISIONAL, then ACCEPT)</div>'
                 if len(shown) < total else "")

    cards = "\n".join(_decision_card(d) for d in shown)
    return f"""<section id="decisions">
  <h2>Decisions</h2>
  <p class="section-note">Evaluated from the default viewer project&apos;s perspective.</p>
  <div class="decision-grid">
{cards}
  </div>
  {more_note}
</section>"""


def _section_side_by_side(net, decisions: list) -> str:
    """
    Show the same author evaluated from two different project viewpoints.
    Illustrates that TrustNet is viewpoint-relative (decentralised).
    """
    # Look for an author that appears in two decisions with different outcomes
    from collections import defaultdict
    by_author: dict = defaultdict(list)
    for d in decisions:
        by_author[_g(d, "author", "")].append(d)

    pair = None
    for author, decs in by_author.items():
        viewers = {_g(d, "viewer", "") for d in decs}
        outcomes = {_g(d, "decision", "") for d in decs}
        if len(viewers) > 1 and len(outcomes) > 1:
            pair = decs[:2]
            break

    if pair is None:
        # Create a synthetic demonstration using real network data
        vouched: set = set()
        for proj in net.projects.values():
            for v in proj.vouches:
                vouched.add(v.handle)
        demo_author = next(iter(vouched), "alice-a000")
        d1 = SimpleNamespace(
            pr_id="pr-001", viewer="proj-01", author=demo_author,
            decision="ACCEPT", belief=0.72, disbelief=0.00, uncertainty=0.28,
            reasons=["Vouched by proj-01 via direct trust edge (T=0.9)"],
            ignored=[], in_campaign=False,
        )
        d2 = SimpleNamespace(
            pr_id="pr-001", viewer="proj-15", author=demo_author,
            decision="PROVISIONAL", belief=0.08, disbelief=0.00, uncertainty=0.92,
            reasons=["No trusted project in proj-15's network vouches this author"],
            ignored=[], in_campaign=False,
        )
        pair = [d1, d2]
        note = '<p class="section-note">Synthetic demonstration &mdash; real decisions available once trust.py is merged.</p>'
    else:
        note = '<p class="section-note">Same PR / author, two project viewpoints, two different answers. This is what &ldquo;decentralised trust&rdquo; means.</p>'

    left  = _decision_card(pair[0])
    right = _decision_card(pair[1])
    author = escape(_g(pair[0], "author", "?"))

    return f"""<section id="side-by-side">
  <h2>Viewpoint-Relative Evaluation</h2>
  {note}
  <p class="section-note">Author: <strong>{author}</strong> &mdash; same person, different verdicts from different projects.</p>
  <div class="sbs-grid">
    <div>{left}</div>
    <div>{right}</div>
  </div>
</section>"""


def _section_campaigns(campaigns: list) -> str:
    if not campaigns:
        return """<section id="campaigns">
  <h2>Campaigns</h2>
  <div class="no-campaigns">No campaigns detected. Run <code>trustnet campaigns</code> to update.</div>
</section>"""

    cards_html = []
    for c in campaigns:
        cid      = escape(_g(c, "id", "?"))
        score    = _fmt(_g(c, "score", 0))
        flagged  = _g(c, "flagged", False)
        evidence = _g(c, "evidence", []) or []
        pr_ids   = _g(c, "pr_ids", []) or []
        projs    = _g(c, "projects", []) or []
        authors  = _g(c, "authors", []) or []
        emb      = _g(c, "embedding_used", False)
        status_badge = _badge("HOLD") if flagged else '<span class="badge badge-provisional">NOT FLAGGED</span>'

        ev_html = "".join(f"<li>{escape(e)}</li>" for e in evidence)
        emb_note = "nomic-embed-text (Ollama)" if emb else "TF-IDF only (Ollama unavailable)"

        cards_html.append(f"""<div class="campaign-card">
  <div class="cc-header">
    <h3>Campaign {escape(cid)}</h3>
    <span>
      {status_badge}
      <span class="score-pill">score {score}</span>
    </span>
  </div>
  <div class="cc-counts">
    <div class="cc-count"><div class="cc-num">{len(pr_ids)}</div><div class="cc-lbl">PRs</div></div>
    <div class="cc-count"><div class="cc-num">{len(projs)}</div><div class="cc-lbl">Projects hit</div></div>
    <div class="cc-count"><div class="cc-num">{len(authors)}</div><div class="cc-lbl">Authors</div></div>
  </div>
  <ul class="ev-list">{ev_html}</ul>
  <div style="margin-top:.5rem;font-size:.75rem;color:var(--text-muted)">
    Similarity model: {escape(emb_note)}
  </div>
</div>""")

    return f"""<section id="campaigns">
  <h2>Campaigns</h2>
  <p class="section-note">Coordinated spam waves detected by PR-text similarity clustering.</p>
  {"".join(cards_html)}
</section>"""


def _section_lab(lab_results: dict) -> str:
    if not lab_results:
        return """<section id="lab">
  <h2>Adversarial Lab</h2>
  <div class="no-lab">Lab results not available. Run <code>trustnet lab</code> to generate.</div>
</section>"""

    rows = []
    for scenario, row in lab_results.items():
        naive    = row.get("naive", "N/A")
        defended = row.get("defended", "N/A")
        if isinstance(naive, (int, float)) and isinstance(defended, (int, float)) and naive:
            reduction = f"{(1 - defended / naive) * 100:.1f}%"
            better_cls = "better" if defended < naive else ""
        else:
            reduction = "N/A"
            better_cls = ""
        fp = row.get("false_positive_rate", "N/A")
        fp_str = f"{fp:.1%}" if isinstance(fp, float) else str(fp)
        rows.append(
            f"<tr><td>{escape(str(scenario))}</td>"
            f"<td>{_fmt(naive)}</td>"
            f'<td class="{better_cls}">{_fmt(defended)}</td>'
            f"<td>{escape(reduction)}</td>"
            f"<td>{escape(fp_str)}</td></tr>"
        )

    rows_html = "\n".join(rows)
    return f"""<section id="lab">
  <h2>Adversarial Lab</h2>
  <p class="section-note">Naive baseline (all projects equal) vs TrustNet defence. Lower is better for attacker scores.</p>
  <div class="lab-wrap">
    <table class="lab-table">
      <thead>
        <tr>
          <th>Scenario</th>
          <th>Naive score</th>
          <th>Defended score</th>
          <th>Reduction</th>
          <th>FP rate (newcomers)</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>
  </div>
</section>"""


def _section_trust_graph(net) -> str:
    """
    Generate an inline SVG showing:
    - Honest projects in a circle with trust edges (solid lines)
    - 3 fake brigade projects off to the side with dashed edges to their target
    - Label: "ignored: source not trusted" on dashed edges
    """
    # Collect honest project IDs only
    honest_ids = sorted(
        pid for pid in net.projects.keys() if pid.startswith("proj-")
    )
    # Show at most 20 for readability
    display_ids = honest_ids[:20]
    n = len(display_ids)
    if n == 0:
        return """<section id="trust-graph">
  <h2>Trust Graph</h2>
  <p class="section-note">No project data available.</p>
</section>"""

    # Circular layout
    CX, CY, R = 340, 310, 240
    W, H = 700, 660
    NODE_R = 14

    pos: dict = {}
    for i, pid in enumerate(display_ids):
        angle = 2 * math.pi * i / n - math.pi / 2  # start at top
        pos[pid] = (CX + R * math.cos(angle), CY + R * math.sin(angle))

    # ---- edges (trust, honest projects only) ----
    edges_svg: list = []
    for pid in display_ids:
        proj = net.projects.get(pid)
        if proj is None:
            continue
        for t in (proj.trusts or []):
            tgt = getattr(t, "project", None)
            if tgt in pos:
                x1, y1 = pos[pid]
                x2, y2 = pos[tgt]
                w = getattr(t, "weight", 0.5)
                edges_svg.append(
                    f'<line class="ge" x1="{x1:.1f}" y1="{y1:.1f}" '
                    f'x2="{x2:.1f}" y2="{y2:.1f}" stroke-opacity="{w:.2f}"/>'
                )

    # ---- fake brigade nodes (3 shown) ----
    brigade_ids = sorted(
        pid for pid in net.projects.keys() if pid.startswith("fake-brigade-")
    )[:3]

    brigade_pos: dict = {}
    bx_base, by_base = W - 90, 120
    for i, bpid in enumerate(brigade_ids):
        brigade_pos[bpid] = (bx_base, by_base + i * 60)

    # Target of the brigade (brigaded_handle) -- find from projects denounces
    brigaded_proj_id = display_ids[0] if display_ids else None
    # Place victim node in center
    victim_x, victim_y = CX, CY
    victim_handle = ""
    for bpid in brigade_ids:
        proj = net.projects.get(bpid)
        if proj and proj.denounces:
            victim_handle = getattr(proj.denounces[0], "handle", "")
            break

    # Dashed brigade edges
    brigade_edges_svg: list = []
    for bpid, (bx, by) in brigade_pos.items():
        mid_x = (bx + victim_x) / 2
        mid_y = (by + victim_y) / 2
        brigade_edges_svg.append(
            f'<line class="ge-ignored" x1="{bx:.1f}" y1="{by:.1f}" '
            f'x2="{victim_x:.1f}" y2="{victim_y:.1f}"/>'
        )
        brigade_edges_svg.append(
            f'<text class="ge-label" x="{mid_x:.1f}" y="{mid_y - 6:.1f}">'
            f'ignored: source not trusted</text>'
        )

    # ---- SVG nodes ----
    nodes_svg: list = []
    for pid, (nx, ny) in pos.items():
        short = pid.replace("proj-", "")
        # label position: push slightly outward from center
        dx = nx - CX
        dy = ny - CY
        dist = math.hypot(dx, dy) or 1
        lx = nx + (dx / dist) * (NODE_R + 9)
        ly = ny + (dy / dist) * (NODE_R + 9)
        anchor = "start" if dx > 10 else ("end" if dx < -10 else "middle")
        nodes_svg.append(
            f'<circle class="gn" cx="{nx:.1f}" cy="{ny:.1f}" r="{NODE_R}"/>'
            f'<text class="gt" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}">{escape(short)}</text>'
        )

    # Victim / target node at center
    if victim_handle:
        nodes_svg.append(
            f'<circle class="gn-victim" cx="{victim_x:.1f}" cy="{victim_y:.1f}" r="{NODE_R + 2}"/>'
            f'<text class="gt" x="{victim_x:.1f}" y="{victim_y + NODE_R + 12:.1f}" '
            f'text-anchor="middle" style="font-size:7px">{escape(victim_handle[:12])}</text>'
            f'<text class="gt" x="{victim_x:.1f}" y="{victim_y + NODE_R + 21:.1f}" '
            f'text-anchor="middle" style="font-size:7px;fill:var(--accept-text)">(brigaded author)</text>'
        )

    # Brigade fake nodes
    for bpid, (bx, by) in brigade_pos.items():
        short = bpid.replace("fake-brigade-", "B")
        nodes_svg.append(
            f'<circle class="gn-fake" cx="{bx:.1f}" cy="{by:.1f}" r="{NODE_R}"/>'
            f'<text class="gt-fake" x="{bx:.1f}" y="{by:.1f}">{escape(short)}</text>'
        )

    svg = (
        f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;max-width:{W}px">\n'
        + "\n".join(edges_svg)
        + "\n"
        + "\n".join(brigade_edges_svg)
        + "\n"
        + "\n".join(nodes_svg)
        + "\n</svg>"
    )

    n_shown = len(display_ids)
    n_total = len(honest_ids)
    note = (f"Showing {n_shown} of {n_total} projects. "
            if n_shown < n_total else "")

    return f"""<section id="trust-graph">
  <h2>Trust Graph</h2>
  <p class="section-note">{escape(note)}Solid edges: project trust &middot; Dashed red edges from brigade nodes (B0&ndash;B2): ignored denounces, source not trusted.</p>
  <div class="graph-wrap">
    {svg}
    <div class="graph-legend">
      <span class="legend-item"><span class="legend-line legend-solid"></span> Trust edge</span>
      <span class="legend-item"><span class="legend-line legend-dashed"></span> Ignored denounce (source not trusted)</span>
      <span class="legend-item">&#x25CF; Honest project &nbsp; &#x25CB; Brigade fake project &nbsp; &#x1F7E2; Brigade target (honest author)</span>
    </div>
  </div>
</section>"""
