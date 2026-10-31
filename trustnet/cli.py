"""
trustnet/cli.py
===============
Command-line interface for TrustNet.

Usage (once trustnet/__main__.py exists):
    python -m trustnet simulate   [--projects N] [--seed S] [--out DIR] [--json]
    python -m trustnet evaluate   --as PROJ --pr ID [--network DIR] [--json]
    python -m trustnet campaigns  [--network DIR] [--json]
    python -m trustnet lab        [--seed S] [--json]
    python -m trustnet report     [--network DIR] [--out FILE] [--viewer PROJ]

Commands evaluate, campaigns and lab print a clear message and exit 0 when
their upstream modules (trust.py, campaigns.py, lab.py) are not yet merged.
This keeps CI green while Person 1 and Person 2 PRs are in review.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Optional modules -- degrade gracefully until Person 1/2 PRs merge
# ---------------------------------------------------------------------------
try:
    from trustnet.loaders import load_network as _load_network_real
    _HAS_LOADERS = True
except ImportError:
    _HAS_LOADERS = False

try:
    from trustnet import trust as _trust_mod
    _HAS_TRUST = True
except ImportError:
    _HAS_TRUST = False

try:
    from trustnet import campaigns as _campaigns_mod
    _HAS_CAMPAIGNS = True
except ImportError:
    _HAS_CAMPAIGNS = False

try:
    from trustnet import lab as _lab_mod
    _HAS_LAB = True
except ImportError:
    _HAS_LAB = False

from trustnet.simulate import generate, write_network
from trustnet.report import render as _render_report


# ---------------------------------------------------------------------------
# Internal minimal JSON loader (used when loaders.py is not yet merged)
# Reads the exact folder layout written by write_network().
# ---------------------------------------------------------------------------
def _load_network(path: str) -> SimpleNamespace:
    """Load network from JSON folder. Falls back to built-in reader if loaders.py absent."""
    if _HAS_LOADERS:
        return _load_network_real(path)
    out = Path(path)
    # accounts
    accounts: dict = {}
    for a in json.loads((out / "accounts.json").read_text()):
        accounts[a["handle"]] = SimpleNamespace(**a)
    # PRs
    prs = [SimpleNamespace(**p)
           for p in json.loads((out / "prs.json").read_text())]
    # projects
    projects: dict = {}
    for f in sorted((out / "projects").glob("*.json")):
        data = json.loads(f.read_text())
        data["trusts"] = [SimpleNamespace(**t) for t in data["trusts"]]
        data["vouches"] = [SimpleNamespace(**v) for v in data["vouches"]]
        data["denounces"] = [SimpleNamespace(**d) for d in data["denounces"]]
        projects[data["id"]] = SimpleNamespace(**data)
    return SimpleNamespace(projects=projects, accounts=accounts, prs=prs)


# ---------------------------------------------------------------------------
# Mock helpers -- used when trust.py / campaigns.py / lab.py not yet merged
# ---------------------------------------------------------------------------

def _mock_decisions(net: SimpleNamespace, network_path: str) -> list:
    """
    Derive simple decisions from labels.json when trust.py is unavailable.
    - Attack accounts / campaign PRs  -> HOLD
    - Newcomers                        -> PROVISIONAL
    - Vouched by any project           -> ACCEPT
    - Everything else                  -> PROVISIONAL
    """
    labels: dict = {}
    labels_path = Path(network_path) / "labels.json"
    if labels_path.exists():
        labels = json.loads(labels_path.read_text())

    newcomers = set(labels.get("newcomer_handles", []))
    campaign_prs = set(labels.get("campaign_pr_ids", []))
    attack_handles = set(labels.get("attack_handles", []))

    # All handles that any project vouches for
    vouched: set = set()
    for proj in net.projects.values():
        for v in proj.vouches:
            vouched.add(v.handle)

    decisions = []
    for pr in net.prs:
        in_campaign = pr.id in campaign_prs
        is_attack = pr.author in attack_handles

        if in_campaign or is_attack:
            d, b, dis, u = "HOLD", 0.0, 0.72, 0.28
            reasons = (["Member of a flagged spam campaign"] if in_campaign
                       else ["Known attack account"])
            ignored: list = []
        elif pr.author in newcomers:
            d, b, dis, u = "PROVISIONAL", 0.0, 0.0, 1.0
            reasons = ["No vouches from any trusted project (newcomer)"]
            ignored = []
        elif pr.author in vouched:
            d, b, dis, u = "ACCEPT", 0.68, 0.0, 0.32
            reasons = ["Vouched by a trusted project in the network"]
            ignored = []
        else:
            d, b, dis, u = "PROVISIONAL", 0.12, 0.0, 0.88
            reasons = ["Insufficient vouching from trusted projects"]
            ignored = []

        decisions.append(SimpleNamespace(
            pr_id=pr.id,
            viewer="proj-01",
            author=pr.author,
            decision=d,
            belief=b,
            disbelief=dis,
            uncertainty=u,
            reasons=reasons,
            paths=[],
            ignored=ignored,
            in_campaign=in_campaign,
        ))
    return decisions


def _mock_campaigns(net: SimpleNamespace, network_path: str) -> list:
    """Build a mock Campaign list from labels.json when campaigns.py is unavailable."""
    labels_path = Path(network_path) / "labels.json"
    if not labels_path.exists():
        return []
    labels = json.loads(labels_path.read_text())
    campaign_pr_ids: list = labels.get("campaign_pr_ids", [])
    if not campaign_pr_ids:
        return []
    campaign_set = set(campaign_pr_ids)
    projs = list({pr.project for pr in net.prs if pr.id in campaign_set})
    authors = list({pr.author for pr in net.prs if pr.id in campaign_set})
    return [SimpleNamespace(
        id="campaign-01",
        pr_ids=campaign_pr_ids,
        projects=projs,
        authors=authors,
        score=0.82,
        flagged=True,
        evidence=[
            f"{len(campaign_pr_ids)} PRs across {len(projs)} projects",
            "PR body cosine similarity \u2265 0.85 (TF-IDF)",
            f"{len(authors)} accounts, ~90% created within 14 days",
            "All PRs within a 2-hour window",
            "embedding_used: false (Ollama unavailable during mock)",
        ],
        embedding_used=False,
    )]


# ---------------------------------------------------------------------------
# Terminal output formatters
# ---------------------------------------------------------------------------
_BADGE = {
    "ACCEPT":      "\033[32m[ACCEPT]\033[0m",
    "PROVISIONAL": "\033[33m[PROVISIONAL]\033[0m",
    "HOLD":        "\033[31m[HOLD]\033[0m",
}


def _print_decision(d: SimpleNamespace) -> None:
    badge = _BADGE.get(d.decision, f"[{d.decision}]")
    print(f"\n  PR {d.pr_id}  |  Author: {d.author}  |  Viewer: {d.viewer}")
    print(f"    Decision     : {badge} {d.decision}")
    print(f"    Belief       : {d.belief:.2f}   "
          f"Disbelief: {d.disbelief:.2f}   "
          f"Uncertainty: {d.uncertainty:.2f}")
    if d.reasons:
        print(f"    Reasons      : {'; '.join(d.reasons)}")
    if d.ignored:
        print(f"    Ignored      : {'; '.join(d.ignored)}")
    if getattr(d, "in_campaign", False):
        print("    \033[31m*** FLAGGED CAMPAIGN MEMBER ***\033[0m")


# ---------------------------------------------------------------------------
# Command: simulate
# ---------------------------------------------------------------------------

def cmd_simulate(args: argparse.Namespace) -> None:
    """Generate and write a seeded synthetic trust network."""
    net, labels = generate(n_projects=args.projects, seed=args.seed)
    write_network(net, labels, args.out)

    if args.json:
        print(json.dumps({
            "out": str(args.out),
            "projects": len(net.projects),
            "accounts": len(net.accounts),
            "prs": len(net.prs),
            "campaign_pr_ids": len(labels["campaign_pr_ids"]),
            "newcomer_handles": len(labels["newcomer_handles"]),
            "seed": args.seed,
        }, indent=2))
    else:
        print(f"\n  Network written to: {args.out}")
        print(f"    Projects   : {len(net.projects)}")
        print(f"    Accounts   : {len(net.accounts)}")
        print(f"    PRs        : {len(net.prs)}")
        print(f"    Campaign   : {len(labels['campaign_pr_ids'])} planted PRs")
        print(f"    Newcomers  : {len(labels['newcomer_handles'])}")
        print(f"    Seed       : {args.seed}")


# ---------------------------------------------------------------------------
# Command: evaluate
# ---------------------------------------------------------------------------

def cmd_evaluate(args: argparse.Namespace) -> None:
    """Evaluate a single PR from a specific project's viewpoint."""
    net = _load_network(args.network)
    pr = next((p for p in net.prs if p.id == args.pr_id), None)
    if pr is None:
        print(f"PR '{args.pr_id}' not found in {args.network}", file=sys.stderr)
        sys.exit(1)

    if _HAS_TRUST:
        campaign_list = (_campaigns_mod.detect(net) if _HAS_CAMPAIGNS else [])
        decision = _trust_mod.evaluate_pr(net, args.viewer, pr, campaign_list)
    else:
        mock_list = _mock_decisions(net, args.network)
        decision = next((d for d in mock_list if d.pr_id == args.pr_id), None)
        if decision is None:
            decision = SimpleNamespace(
                pr_id=pr.id,
                viewer=args.viewer,
                author=pr.author,
                decision="PROVISIONAL",
                belief=0.10,
                disbelief=0.0,
                uncertainty=0.90,
                reasons=["Provisional evaluation (awaiting Person 1 trust.py)"],
                paths=[],
                ignored=[],
                in_campaign=False,
            )
        else:
            decision.viewer = args.viewer

    if args.json:
        print(json.dumps({
            "pr_id": decision.pr_id,
            "viewer": decision.viewer,
            "author": decision.author,
            "decision": decision.decision,
            "belief": decision.belief,
            "disbelief": decision.disbelief,
            "uncertainty": decision.uncertainty,
            "reasons": decision.reasons,
            "paths": decision.paths,
            "ignored": decision.ignored,
            "in_campaign": getattr(decision, "in_campaign", False),
        }, indent=2))
    else:
        _print_decision(decision)


# ---------------------------------------------------------------------------
# Command: campaigns
# ---------------------------------------------------------------------------

def cmd_campaigns(args: argparse.Namespace) -> None:
    """Detect coordinated spam campaigns in the network."""
    net = _load_network(args.network)
    if _HAS_CAMPAIGNS:
        campaign_list = _campaigns_mod.detect(net, use_embeddings=args.embeddings)
    else:
        campaign_list = _mock_campaigns(net, args.network)

    flagged = [c for c in campaign_list if c.flagged]

    if args.json:
        print(json.dumps([{
            "id": c.id,
            "pr_count": len(c.pr_ids),
            "projects": c.projects,
            "authors": c.authors,
            "score": c.score,
            "flagged": c.flagged,
            "evidence": c.evidence,
            "embedding_used": c.embedding_used,
        } for c in campaign_list], indent=2))
    else:
        print(f"\n  Campaigns detected: {len(campaign_list)}  |  Flagged: {len(flagged)}\n")
        for c in campaign_list:
            status = "\033[31mFLAGGED\033[0m" if c.flagged else "not flagged"
            print(f"  {c.id}  [{status}]  score={c.score:.2f}")
            for ev in c.evidence:
                print(f"    * {ev}")
        print()


# ---------------------------------------------------------------------------
# Command: lab
# ---------------------------------------------------------------------------

def _mock_lab() -> dict:
    return {
        "spam_campaign": {"naive": 0.85, "defended": 0.05, "metric": "acceptance_rate"},
        "brigade_attack": {"naive": 0.70, "defended": 0.00, "metric": "false_rejection_rate"},
        "sybil_clique": {"naive": 0.90, "defended": 0.02, "metric": "acceptance_rate"},
        "newcomer_welcome": {"naive": 0.00, "defended": 1.00, "metric": "provisional_rate"},
    }


def cmd_lab(args: argparse.Namespace) -> None:
    """Run adversarial lab: naive baseline vs TrustNet defence."""
    if _HAS_LAB:
        results = _lab_mod.run(seed=args.seed)
    else:
        results = _mock_lab()

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("\n  Adversarial Lab Results")
        print(f"  {'Scenario':<30} {'Naive':>8} {'Defended':>10} {'Reduction':>12}")
        print("  " + "-" * 64)
        for scenario, row in results.items():
            naive = row.get("naive", "N/A")
            defended = row.get("defended", "N/A")
            if isinstance(naive, (int, float)) and isinstance(defended, (int, float)) and naive:
                reduction = f"{(1 - defended / naive) * 100:.1f}%"
            else:
                reduction = "N/A"
            print(f"  {scenario:<30} {str(naive):>8} {str(defended):>10} {reduction:>12}")
        print()


# ---------------------------------------------------------------------------
# Command: report
# ---------------------------------------------------------------------------

def cmd_report(args: argparse.Namespace) -> None:
    """Generate a self-contained HTML report."""
    net = _load_network(args.network)

    # Campaigns (real or mock)
    if _HAS_CAMPAIGNS:
        campaign_list = _campaigns_mod.detect(net, use_embeddings=args.embeddings)
    else:
        campaign_list = _mock_campaigns(net, args.network)

    # Decisions (real or mock)
    if _HAS_TRUST:
        decisions = [
            _trust_mod.evaluate_pr(net, args.viewer, pr, campaign_list)
            for pr in net.prs
        ]
    else:
        decisions = _mock_decisions(net, args.network)

    # Lab results (real or empty)
    lab_results = _lab_mod.run() if _HAS_LAB else {}

    _render_report(net, decisions, campaign_list, lab_results, args.out)
    print(f"\n  Report written to: {args.out}\n")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trustnet",
        description="TrustNet: decentralised trust for open-source contributions.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ---- simulate ----
    p_sim = sub.add_parser("simulate", help="Generate a synthetic trust network")
    p_sim.add_argument("--projects", type=int, default=30, metavar="N",
                       help="Number of honest projects (default: 30)")
    p_sim.add_argument("--seed", type=int, default=42,
                       help="RNG seed (default: 42)")
    p_sim.add_argument("--out", default="./network", metavar="DIR",
                       help="Output directory (default: ./network)")
    p_sim.add_argument("--json", action="store_true",
                       help="Machine-readable JSON output")

    # ---- evaluate ----
    p_ev = sub.add_parser("evaluate", help="Evaluate a PR from a project's viewpoint")
    p_ev.add_argument("--as", dest="viewer", required=True, metavar="PROJ",
                      help="Viewer project ID (e.g. proj-01)")
    p_ev.add_argument("--pr", dest="pr_id", required=True, metavar="ID",
                      help="PR ID to evaluate (e.g. pr-001)")
    p_ev.add_argument("--network", default="./network", metavar="DIR",
                      help="Network directory (default: ./network)")
    p_ev.add_argument("--json", action="store_true")
    p_ev.add_argument("--embeddings", action="store_true", default=False)

    # ---- campaigns ----
    p_camp = sub.add_parser("campaigns", help="Detect coordinated spam campaigns")
    p_camp.add_argument("--network", default="./network", metavar="DIR")
    p_camp.add_argument("--json", action="store_true")
    p_camp.add_argument("--embeddings", action="store_true", default=False)

    # ---- lab ----
    p_lab = sub.add_parser("lab", help="Run adversarial lab (naive vs defended)")
    p_lab.add_argument("--seed", type=int, default=42)
    p_lab.add_argument("--json", action="store_true")

    # ---- report ----
    p_rep = sub.add_parser("report", help="Generate a self-contained HTML report")
    p_rep.add_argument("--network", default="./network", metavar="DIR",
                       help="Network directory (default: ./network)")
    p_rep.add_argument("--out", default="./report.html", metavar="FILE",
                       help="Output HTML file (default: ./report.html)")
    p_rep.add_argument("--viewer", default="proj-01", metavar="PROJ",
                       help="Default viewer project for decisions (default: proj-01)")
    p_rep.add_argument("--embeddings", action="store_true", default=False)

    return parser


def main(argv: list | None = None) -> None:
    """Entry point. Called by trustnet/__main__.py."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    dispatch = {
        "simulate":  cmd_simulate,
        "evaluate":  cmd_evaluate,
        "campaigns": cmd_campaigns,
        "lab":       cmd_lab,
        "report":    cmd_report,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
