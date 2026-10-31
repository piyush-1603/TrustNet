# TrustNet

> **Decentralized Trust Network for Open-Source Contributions**
> Team Sophons · Hacktoberfest 2026 Hack Day, Sonipat · Problem 7

TrustNet lets open-source projects share vouch and denounce records, decide — each from
their **own point of view** — what to do with a contributor, and detect coordinated spam
campaigns across projects. A contributor with no history is treated as **unknown**, never
as distrusted.

---

## Table of contents

- [Install](#install)
- [Quick start](#quick-start)
- [Commands](#commands)
- [Design decisions](#design-decisions)
- [What is not built](#what-is-not-built)
- [Project layout](#project-layout)
- [Team](#team)

---

## Install

**Requirements:** Python 3.11+, [Ollama](https://ollama.com) (optional — for embeddings)

```bash
git clone https://github.com/piyush-1603/TrustNet.git
cd TrustNet
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

To enable the `nomic-embed-text` embedding path (optional but recommended for the demo):

```bash
ollama pull nomic-embed-text
```

If Ollama is not running, TrustNet falls back to TF-IDF automatically and says so in the output.

---

## Quick start

```bash
# 1. Generate a simulated network (30 projects, planted attacks, deterministic)
python -m trustnet simulate --projects 30 --seed 42

# 2. Evaluate a contributor's PR from a specific project's point of view
python -m trustnet evaluate --as proj-01 --pr pr-042

# 3. Detect coordinated spam campaigns
python -m trustnet campaigns

# 4. Run the adversarial lab (naive vs defended comparison)
python -m trustnet lab

# 5. Write a self-contained HTML report (report.html)
python -m trustnet report
```

`simulate`, `evaluate`, `campaigns` and `lab` also accept `--json` for machine-readable output.

---

## Commands

| Command | What it does |
|---|---|
| `simulate` | Generates a seeded network with planted attacks in `network/` |
| `evaluate --as PROJ --pr ID` | Evaluates PR `ID` from project `PROJ`'s viewpoint |
| `campaigns` | Clusters near-duplicate PRs and flags coordinated campaigns |
| `lab` | Runs four attack scenarios; prints naive vs defended table |
| `report` | Renders a self-contained HTML report with all results |

---

## Design decisions

### 1. How does transitive trust work?

Trust from project A to project C through B is computed as:

```
T(A, C)  =  weight(A→B) × weight(B→C) × 0.6
```

The `0.6` decay applies for each hop after the first. Paths longer than 3 hops are
discarded. If multiple paths reach the same target, the **maximum** path value is used —
never the sum. The viewer always trusts itself at `1.0`.

This models real-world wariness: you trust your direct allies most, their allies a bit
less, and you never blindly inherit trust from chains you cannot audit.

### 2. How does trust propagate through the network?

TrustNet performs a bounded best-path search (up to 3 hops, cycle-safe). It computes
belief `b` and disbelief `d` from vouching and denouncing projects:

```
b = 1 − ∏(1 − 0.8 · Tᵢ)   over up to 3 projects with Tᵢ ≥ 0.25 that vouch
d = same formula             over projects that denounce
u = max(0, 1 − b − d)       uncertainty; b and d are used as computed, never rescaled
```

Decision rule:
- `d ≥ 0.5` and `d > b` → **HOLD**
- `b ≥ 0.5` → **ACCEPT**
- otherwise → **PROVISIONAL** (review queue)
- member of a flagged campaign → **HOLD** (overrides everything)

All thresholds live in `policy.json` and are our own defaults, tuned on our simulation.

### 3. How are fake denounces handled?

Denounces from projects with trust `T < 0.25` from the viewer are **ignored entirely**
and reported as `"ignored: source not trusted"` in the output. A denounce without an
`evidence_url` counts at half weight. An expired denounce counts zero.

This means a brigade of fake projects denouncing an honest contributor has no effect as
long as the viewer does not trust those projects.

### 4. What happens to a brand-new contributor?

A contributor with no vouches and no denounces anywhere in the network gets `PROVISIONAL`.
They are never auto-rejected for lack of history. `PROVISIONAL` means the project's normal
review process applies — a human looks at the PR.

### 5. Where is the decentralization?

The same author can receive **two different decisions** from two different projects,
because each project chooses which other projects it trusts. There is no central
authority. Project A's view of contributor X depends entirely on A's own trust graph —
not on any global score.

### 6. Why is AI text detection alone not enough?

A spam campaign can reword its PRs slightly, defeating keyword filters and even some
classifiers. TrustNet uses `nomic-embed-text` embeddings (or TF-IDF as a fallback) to
measure **semantic similarity** across PRs. Two reworded variants of the same spam body
will have a high cosine similarity in embedding space even when they share few exact
words. The campaign detector then clusters these PRs, checks account ages, project spread,
and timing — a combination that is much harder to evade than text matching alone.

Crucially, the model only supplies a similarity score. All trust and campaign decisions
are made by **deterministic rules** in `policy.json`. This keeps the system auditable and
explainable.

---

## What is not built

- **Vouch-file adapter:** A Ghostty-style `+handle` / `-handle` flat-file format is
  sketched in the design but not implemented in the loader.
- **SVG trust graph in the terminal:** The HTML report includes an SVG graph; the CLI
  does not render one.
- **Real open-source data:** All networks are simulated or hand-crafted. The loader is
  designed to read real data once the organizers share their format.
- **Collusion cap:** The design notes a stretch goal to cap how much two mutually-trusting
  projects can inflate each other's score. Not implemented.
- **Extra lab scenarios:** The lab covers four attack types. Additional scenarios
  (e.g. gradual reputation laundering) are not yet included.

---

## Project layout

```
trustnet/           Python package
  models.py         dataclasses: Project, Account, PR, Network, Decision, Campaign
  loaders.py        load_network(path) -> Network
  trust.py          project_trust, evaluate_author, evaluate_pr, naive_score
  similarity.py     TF-IDF + nomic-embed-text cosine similarity
  campaigns.py      coordinated campaign detector
  lab.py            adversarial lab (naive vs defended)
  simulate.py       seeded network generator
  report.py         static HTML report renderer
  cli.py            command-line interface
policy.json         all numeric thresholds (decay, hops, weights, campaign cutoffs)
tests/
  fixtures/         four hand-made networks (newcomer, brigade, bulk_bump, campaign)
  test_smoke.py     package import + PR template checks
  test_fixtures.py  fixture structure and scenario validation
  test_trust.py     trust engine unit tests
  test_loaders.py   loader tests
  test_similarity.py  TF-IDF + mocked Ollama tests
  test_campaigns.py   campaign detector tests
  test_lab.py       lab output validation
docs/
  PLAN.md           single source of truth for the build plan
  DESIGN.md         all formulas written out
  DEMO.md           8-minute demo script
  MENTOR_NOTES.md   mentor Q&A (format, models, nomic-embed-text)
examples/           real pipeline input + output committed from make_examples.sh
.github/
  workflows/ci.yml  Python 3.11, pip install, pytest -q
  pull_request_template.md
```

---

## Team

| Person | Role |
|---|---|
| Shaurya Pratap Singh | Trust engine, integration, merges |
| Anubhav Jaiswal | Similarity, campaign detection, adversarial lab |
| Piyush Tharwani | Simulator, HTML report, CLI, examples |
| Arnav Gupta | CI, docs, fixtures, submission |

**Model used:** `nomic-embed-text` (open-weight) via [Ollama](https://ollama.com).
All trust decisions are deterministic rules; the model only provides a similarity score.
