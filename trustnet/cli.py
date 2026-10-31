"""
trustnet/cli.py
===============
Command-line interface for TrustNet.

Usage:
    python -m trustnet simulate   [--projects N] [--seed S] [--out DIR] [--json]
    python -m trustnet evaluate   --as PROJ --pr ID [--network DIR] [--json] [--no-embeddings]
                                  [--advisory FILE ...] [--no-local-detection]
    python -m trustnet campaigns  [--network DIR] [--json] [--no-embeddings]
    python -m trustnet advisory   --as PROJ [--network DIR] [--out FILE] [--no-embeddings]
    python -m trustnet lab        [--seed S] [--json]
    python -m trustnet ablation   [--json]
    python -m trustnet fanout     [--json]
    python -m trustnet report     [--network DIR] [--out FILE] [--viewer PROJ] [--no-embeddings]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from trustnet import ablation as _ablation_mod
from trustnet import fanout_demo as _fanout_mod
from trustnet.advisory import build_advisory, load_advisory
from trustnet.loaders import load_network, load_policy
from trustnet import trust as _trust_mod
from trustnet import campaigns as _campaigns_mod
from trustnet import lab as _lab_mod
from trustnet.simulate import generate, write_network
from trustnet.report import render as _render_report


def _load_network(path: str):
    try:
        return load_network(path)
    except (ValueError, FileNotFoundError, OSError) as exc:
        print(f"Error loading network from '{path}': {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Terminal output formatters
# ---------------------------------------------------------------------------
_BADGE = {
    "ACCEPT":      "\033[32m[ACCEPT]\033[0m",
    "PROVISIONAL": "\033[33m[PROVISIONAL]\033[0m",
    "HOLD":        "\033[31m[HOLD]\033[0m",
}


def _print_decision(d) -> None:
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
    if getattr(d, "next_steps", None):
        print(f"    Path to trust: {'; '.join(d.next_steps)}")
    if getattr(d, "in_campaign", False):
        print("    \033[31m*** FLAGGED CAMPAIGN MEMBER ***\033[0m")


# ---------------------------------------------------------------------------
# Command: simulate
# ---------------------------------------------------------------------------

def cmd_simulate(args: argparse.Namespace) -> None:
    """Generate and write a seeded synthetic trust network."""
    if args.projects < 1:
        print("Error: --projects must be at least 1", file=sys.stderr)
        sys.exit(1)
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
        print(f"Error: PR '{args.pr_id}' not found in {args.network}", file=sys.stderr)
        sys.exit(1)

    advisories = []
    for path in args.advisory:
        try:
            advisories.append(load_advisory(path))
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
    # --no-local-detection: this project did not run the detector; it relies on advisories it imports.
    campaign_list = [] if args.no_local_detection else _campaigns_mod.detect(net, use_embeddings=args.embeddings)
    decision = _trust_mod.evaluate_pr(net, args.viewer, pr, campaign_list, advisories=advisories)

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
            "next_steps": decision.next_steps,
        }, indent=2))
    else:
        _print_decision(decision)


# ---------------------------------------------------------------------------
# Command: campaigns
# ---------------------------------------------------------------------------

def cmd_campaigns(args: argparse.Namespace) -> None:
    """Detect coordinated spam campaigns in the network."""
    net = _load_network(args.network)
    campaign_list = _campaigns_mod.detect(net, use_embeddings=args.embeddings)
    flagged = [c for c in campaign_list if c.flagged]

    if args.json:
        print(json.dumps([{
            "id": c.id,
            "kind": getattr(c, "kind", "text"),
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
# Command: advisory
# ---------------------------------------------------------------------------

def cmd_advisory(args: argparse.Namespace) -> None:
    """Publish this project's flagged campaigns as an advisory file other projects can import."""
    net = _load_network(args.network)
    if args.viewer not in net.projects:
        print(f"Error: project '{args.viewer}' not found in {args.network}", file=sys.stderr)
        sys.exit(1)
    campaign_list = _campaigns_mod.detect(net, use_embeddings=args.embeddings)
    advisory = build_advisory(args.viewer, campaign_list, load_policy()[1])
    Path(args.out).write_text(json.dumps(advisory, indent=2) + "\n")
    flagged = advisory["campaigns"]
    print(f"\n  Advisory from {args.viewer} written to: {args.out}")
    print(f"    Flagged campaigns : {len(flagged)}")
    print(f"    Accounts listed   : {sum(len(c['authors']) for c in flagged)}")
    print("    Importers honor it only if they trust the issuer.\n")


# ---------------------------------------------------------------------------
# Command: lab
# ---------------------------------------------------------------------------

def cmd_lab(args: argparse.Namespace) -> None:
    """Run adversarial lab: naive baseline vs TrustNet defence."""
    results = _lab_mod.run(seed=args.seed)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(results.get("markdown", ""))


# ---------------------------------------------------------------------------
# Command: ablation
# ---------------------------------------------------------------------------

def cmd_ablation(args: argparse.Namespace) -> None:
    """Show what the model adds: the same reworded campaign with the model off and on."""
    result = _ablation_mod.run()
    if args.json:
        print(json.dumps(result, indent=2))
        return
    off, on = result["model_off"], result["model_on"]
    print(f"\n  One spam message in {result['spam_prs']} different wordings, {result['spam_prs']} new accounts, "
          f"{result['spam_prs']} projects, 2 hours, hidden among {result['honest_prs']} ordinary PRs.\n")
    print(f"    Model OFF (keyword matching only): {'FLAGGED' if off['flagged'] else 'not flagged'}"
          f"  ({len(off['pr_ids'])} PRs linked)")
    if on is None:
        print("    Model ON  (nomic-embed-text)     : unavailable. Start Ollama (ollama serve) and pull nomic-embed-text.")
    else:
        print(f"    Model ON  (nomic-embed-text)     : {'FLAGGED' if on['flagged'] else 'not flagged'}"
              f"  ({len(result['spam_ids_found_with_model'])} of {result['spam_prs']} spam PRs found, "
              f"{len(result['honest_flagged_with_model'])} ordinary PRs wrongly flagged)")
    print()


# ---------------------------------------------------------------------------
# Command: fanout
# ---------------------------------------------------------------------------

def cmd_fanout(args: argparse.Namespace) -> None:
    """Show the text-independent behavior flag on three people who each send ten different PRs."""
    result = _fanout_mod.run()
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(f"\n  Each person sends {result['prs_per_person']} completely different PRs to {result['projects']} projects "
          f"in about two hours. Text campaigns found: {len(result['text_campaigns'])}. Viewer: {result['viewer']}.\n")
    for row in result["people"]:
        vouch = "vouched by the viewer" if row["vouched_by_viewer"] else "nobody vouches"
        flag = "FLAGGED" if row["behavior_flag"] else "not flagged"
        note = "  (flag overridden by trusted vouches)" if any("overridden" in i for i in row["ignored"]) else ""
        print(f"    {row['handle']:<16} {row['account_age_days']:>3} days old, {vouch:<22} behavior: {flag:<11} -> {row['decision']}{note}")
    print()


# ---------------------------------------------------------------------------
# Command: report
# ---------------------------------------------------------------------------

def cmd_report(args: argparse.Namespace) -> None:
    """Run the analysis pipeline and generate its inspectable HTML report."""
    print("\n  [1/4] Loading network snapshot...")
    net = _load_network(args.network)
    print(f"        {len(net.projects)} repositories, {len(net.accounts)} accounts, {len(net.prs)} PRs loaded.")

    print("  [2/4] Scanning PR text and campaign behavior...")
    campaign_list = _campaigns_mod.detect(net, use_embeddings=args.embeddings)
    flagged = [c for c in campaign_list if c.flagged]
    print(f"        {len(campaign_list)} campaign groups; {sum(len(c.pr_ids) for c in flagged)} PRs in flagged groups.")

    print(f"  [3/4] Evaluating PRs from {args.viewer}'s point of view...")
    decisions = [
        _trust_mod.evaluate_pr(net, args.viewer, pr, campaign_list)
        for pr in net.prs
    ]
    print("        " + " · ".join(f"{label}: {sum(d.decision == label for d in decisions)}"
                                  for label in ("ACCEPT", "PROVISIONAL", "HOLD")))

    print("  [4/4] Running adversarial regression fixtures...")
    lab_results = _lab_mod.run(use_embeddings=args.embeddings)
    scenarios = lab_results.get("scenarios", {})
    print(f"        {len(scenarios)} scenarios completed, including the trusted-source failure control.")

    print("  Writing repository and evidence explorer...")
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
    p_ev.add_argument("--embeddings", dest="embeddings", action="store_true", default=True,
                      help="Use embeddings if available (default: True)")
    p_ev.add_argument("--no-embeddings", dest="embeddings", action="store_false",
                      help="Disable embeddings and use TF-IDF fallback")
    p_ev.add_argument("--advisory", action="append", default=[], metavar="FILE",
                      help="Campaign advisory to import (repeatable); honored only if its issuer is trusted")
    p_ev.add_argument("--no-local-detection", action="store_true",
                      help="Skip running the campaign detector here; rely on imported advisories")

    # ---- campaigns ----
    p_camp = sub.add_parser("campaigns", help="Detect coordinated spam campaigns")
    p_camp.add_argument("--network", default="./network", metavar="DIR")
    p_camp.add_argument("--json", action="store_true")
    p_camp.add_argument("--embeddings", dest="embeddings", action="store_true", default=True,
                        help="Use embeddings if available (default: True)")
    p_camp.add_argument("--no-embeddings", dest="embeddings", action="store_false",
                        help="Disable embeddings and use TF-IDF fallback")

    # ---- advisory ----
    p_adv = sub.add_parser("advisory", help="Publish flagged campaigns as a shareable advisory file")
    p_adv.add_argument("--as", dest="viewer", required=True, metavar="PROJ",
                       help="Issuing project ID (e.g. proj-01)")
    p_adv.add_argument("--network", default="./network", metavar="DIR")
    p_adv.add_argument("--out", default="./advisory.json", metavar="FILE")
    p_adv.add_argument("--embeddings", dest="embeddings", action="store_true", default=True,
                       help="Use embeddings if available (default: True)")
    p_adv.add_argument("--no-embeddings", dest="embeddings", action="store_false",
                       help="Disable embeddings and use TF-IDF fallback")

    # ---- fanout ----
    p_fan = sub.add_parser("fanout", help="Show the text-independent behavior flag on three people")
    p_fan.add_argument("--json", action="store_true")

    # ---- ablation ----
    p_abl = sub.add_parser("ablation", help="Show what the model adds: same campaign, model off vs on")
    p_abl.add_argument("--json", action="store_true")

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
    p_rep.add_argument("--embeddings", dest="embeddings", action="store_true", default=True,
                       help="Use embeddings if available (default: True)")
    p_rep.add_argument("--no-embeddings", dest="embeddings", action="store_false",
                       help="Disable embeddings and use TF-IDF fallback")

    return parser


def main(argv: list | None = None) -> None:
    """Entry point. Called by trustnet/__main__.py."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    dispatch = {
        "simulate":  cmd_simulate,
        "evaluate":  cmd_evaluate,
        "campaigns": cmd_campaigns,
        "advisory":  cmd_advisory,
        "ablation":  cmd_ablation,
        "fanout":    cmd_fanout,
        "lab":       cmd_lab,
        "report":    cmd_report,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
