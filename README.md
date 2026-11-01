# TrustNet

[![CI](https://github.com/piyush-1603/TrustNet/actions/workflows/ci.yml/badge.svg)](https://github.com/piyush-1603/TrustNet/actions/workflows/ci.yml)

> **Decentralized Trust Network for Open-Source Contributions**
> Team Sophons · Hacktoberfest 2026 Hack Day, Sonipat · Problem 7

TrustNet lets open-source projects share vouch and denounce records, decide — each from
their **own point of view** — what to do with a contributor, and detect coordinated spam
campaigns across projects. A contributor with no history is treated as **unknown**, never
as distrusted.

**Results at a glance** (simulated network, seed 42, reproducible with the commands below)

| | |
|---|---|
| Simulated network | 39 projects, 238 accounts, 217 PRs, with planted attacks and 15 newcomers |
| Planted spam campaign | 38 PRs from 20 new accounts across 25 projects found, with the open model on (36 found with keyword matching only) |
| Reworded spam (`ablation`) | 12 of 12 found with the model on, 0 found with it off; 0 of 30 ordinary PRs flagged |
| Attack lab (`lab`) | 4 of 5 attacks defended; the 5th (a compromised trusted project) is a failing control, reported as such |
| Newcomers | No history means PROVISIONAL (human review), never HOLD |
| Tests | 213 pass in CI (1 more needs Ollama); every command in this README is exercised |

All figures come from synthetic data. They are regression results, not evidence of general attack resistance.

---

## What makes TrustNet different

1. **Every answer is relative to the asking project.** The same pull request can be ACCEPT for one
   project and PROVISIONAL for another. There is no global score and no central server.
2. **Newcomers are unknown, not guilty, and they get a way forward.** No history means PROVISIONAL
   (a review queue), never a block. The decision card also says what would move them to ACCEPT:
   "one vouch from a project you trust at 0.63 or more, for example proj-02 (0.79)".
3. **Brigading does nothing.** Denounces from projects you do not trust are ignored and listed. A
   denounce without evidence counts half; an expired one counts zero.
4. **Evidence travels, authority does not.** A project that finds a spam campaign publishes an
   advisory file. Another project imports it, and it only counts if that project already trusts the
   issuer. A fake project cannot get anyone held.
5. **Vouching for spam costs you.** If a project vouched for an account that is later flagged in a
   campaign, its other vouches count half. Projects that merely received the spam are not penalised.
6. **A real open model, kept in its place.** `nomic-embed-text` (via Ollama) catches heavily reworded spam
   that keyword matching misses entirely (`python -m trustnet ablation` runs both side by side);
   deterministic rules in `policy.json` make every decision, and every decision shows its trust path.
7. **A second alarm that ignores the text.** One new account opening PRs in five or more projects within
   six hours is flagged even when no two PRs share a word (`python -m trustnet fanout`). A strong vouch from
   a trusted project overrides it, so a vouched newcomer who is just getting started is not held.
8. **An honest benchmark.** The attack lab compares naive counting with TrustNet on five synthetic
   attacks, and includes one where the defense fails by design (a compromised trusted source).
   These are regression fixtures, not general attack-resistance claims.

---

## Table of contents

- [What makes TrustNet different](#what-makes-trustnet-different)
- [Install](#install)
- [Quick start](#quick-start)
- [Commands](#commands)
- [Input data format](#input-data-format)
- [Design decisions](#design-decisions)
- [Problem statement coverage](#problem-statement-coverage)
- [Testing](#testing)
- [What is not built](#what-is-not-built)
- [Responsible use and AI disclosure](#responsible-use-and-ai-disclosure)
- [Project layout](#project-layout)
- [Team](#team)
- [License](#license)

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

Run these from the repository folder, **inside the virtual environment** from the Install step (your prompt starts with `(.venv)`). On macOS plain `python` only exists inside it; outside, use `python3.11`.
For the model path, `ollama serve` must be running in another terminal tab. Without it everything still works with keyword matching and says `embedding_used: false`.

```bash
# 1. Generate a simulated network (30 projects, planted attacks, deterministic)
python -m trustnet simulate --projects 30 --seed 42

# 2. Evaluate a contributor's PR from a specific project's point of view
python -m trustnet evaluate --as proj-01 --pr pr-042

# 3. Detect coordinated spam campaigns
python -m trustnet campaigns

# 3b. Share what one project found, and let another project use it
python -m trustnet advisory --as proj-01 --out advisory.json
python -m trustnet evaluate --as proj-02 --pr pr-151 --no-local-detection --advisory advisory.json

# 3c. What does the open model add? Same reworded campaign, model off vs on
python -m trustnet ablation

# 3d. A spammer who never repeats a word: text-independent behavior flag
python -m trustnet fanout

# 4. Run the adversarial lab (naive vs defended comparison)
python -m trustnet lab

# 5. Write a self-contained HTML report (report.html)
python -m trustnet report
```

`simulate`, `evaluate`, `campaigns`, `lab`, `ablation` and `fanout` also accept `--json` for machine-readable output.
Committed outputs of a real run (with the model) are in [`examples/`](examples/); regenerate them with `bash examples/make_examples.sh`.

---

## Commands

| Command | What it does |
|---|---|
| `simulate` | Generates a seeded network with planted attacks in `network/` |
| `evaluate --as PROJ --pr ID` | Evaluates PR `ID` from project `PROJ`'s viewpoint |
| `evaluate ... --advisory FILE` | Also imports a campaign advisory; honored only if its issuer is trusted. Repeatable. |
| `evaluate ... --no-local-detection` | Skips the local detector, to show what an imported advisory alone does |
| `campaigns` | Clusters near-duplicate PRs and flags coordinated campaigns |
| `advisory --as PROJ --out FILE` | Publishes the flagged campaigns as a shareable advisory file |
| `fanout` | Three people, ten different PRs each: shows the text-independent behavior flag and the vouch override |
| `ablation` | Same reworded campaign with the model off and on: shows what the model adds |
| `lab` | Runs five synthetic attack scenarios (four defended, one failing control); prints naive vs defended decisions |
| `report` | Writes one offline HTML file: a searchable explorer of projects, PR decisions with trust paths, campaigns and the lab fixtures |

---

## Input data format

TrustNet reads a folder of plain JSON files (a full description is in [`docs/PLAN.md`](docs/PLAN.md)):

```
network/
  projects/<id>.json   id, name, trusts [{project, weight}], vouches [{handle, date, evidence_url}],
                       denounces [{handle, reason_code, evidence_url, date, expires}]
  accounts.json        [{handle, created_at}]
  prs.json             [{id, project, author, created_at, title, body, diff_text}]
```

`loaders.py` validates every file and rejects bad input with an error that names the file and field. Only handles,
reason codes, evidence links and dates are stored for a denounce, which keeps personal data to a minimum.

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
- member of a flagged text campaign, or listed in an advisory from a trusted project → **HOLD**
- flagged by the behavior alarm (see 8) → **HOLD**, unless trusted projects already vouch strongly enough to ACCEPT

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
review process applies — a human looks at the PR. The decision also carries a **path to
trust**: how strong a vouch would lift the author to ACCEPT, and which projects the viewer
trusts enough to give it.

### 5. Where is the decentralization?

The same author can receive **two different decisions** from two different projects,
because each project chooses which other projects it trusts. There is no central
authority. Project A's view of contributor X depends entirely on A's own trust graph —
not on any global score.

### 6. Why is AI text detection alone not enough?

A spam campaign can reword its PRs, defeating keyword filters. TrustNet compares each PR's
title, description and a short view of its change (at most 1,500 characters) using
`nomic-embed-text` embeddings, with TF-IDF as the offline fallback. Reworded variants of one
message share almost no words (keyword score about 0.1) but score about 0.8 to 0.9 with the model.
`python -m trustnet ablation` shows it: the same 12 reworded PRs are missed with the model off and
found with it on, with no ordinary PR flagged. The campaign detector then checks account ages,
project spread and timing, which is much harder to evade than text matching alone.

Honest limits: the model's score threshold (0.80) was chosen on 42 hand-written descriptions, not a
population; generic look-alike PRs (such as typo fixes) can score high, so similar text alone never
flags anything.

Crucially, the model only supplies a similarity score. All trust and campaign decisions
are made by **deterministic rules** in `policy.json`. This keeps the system auditable and
explainable.

### 7. How do projects exchange trust information?

Two ways, both without a central server. First, every project's vouch and denounce lists are
public files that other projects read, weighted by how much the reader trusts the owner.
Second, a project that detects a campaign can publish an **advisory** (`trustnet advisory`):
a small JSON file with the flagged accounts and the evidence. A project that imports it
(`evaluate --advisory`) holds those accounts only if it already trusts the issuer; otherwise the
advisory is ignored and says so.

### 8. What if the spammer writes a different PR every time?

The text detector sees nothing, so there is a second, text-independent alarm: one account under 14 days
old that opens PRs in at least five different projects within six hours is flagged (`fanout_min_projects`
in `policy.json`). An unvouched flagged account is held for review. An account that trusted projects
already vouch for strongly enough to ACCEPT is not held, so honest newcomers are protected, and a flag
never costs the people who vouched. It does not catch an old account, a patient spammer who spreads PRs
over days, or many accounts that each send one different PR.

### 9. What stops projects from vouching for spammers or colluding?

Trust is relative to the viewer, so colluding projects only affect people who already trust
them. Within a viewer's own trust graph, a project that vouched for an account later flagged in a
campaign has its other vouches discounted (`trust.flagged_endorser_factor`, default 0.5).
Projects that only received the spam are not penalised. The lab includes one case that still
defeats the defense: a project the viewer trusts directly that turns malicious.

---

## Problem statement coverage

| Requirement (Problem 7) | Where it is covered |
|---|---|
| Public vouch and denounce records per project | `network/projects/<id>.json`, validated by `loaders.py` |
| Projects exchange trust information | Trust edges between projects, plus campaign advisories (`advisory`, `--advisory`) |
| Identify suspicious patterns across projects | Campaign detector (text similarity, project spread, time window, account age) and a text-independent fan-out flag for one new account across many projects |
| Detect coordinated spam campaigns | `campaigns`; 38-PR planted campaign found with `nomic-embed-text` |
| No central authority | Decisions are computed per viewer from public files; advisories only count from trusted issuers |
| Fair evaluation of new contributors | PROVISIONAL, never HOLD for lack of history; path-to-trust hint |
| Do not exclude legitimate newcomers | 15 simulated newcomers: 0 HOLD; legitimate bulk bump not flagged |
| Malicious denounces | Untrusted sources ignored; evidence and expiry matter |
| Transitive trust (A trusts B trusts C) | Best path, 0.6 decay per hop, 3 hops, never summed |
| Why AI-text detection alone is not enough | Behavior signals (similarity, account age, spread, timing) |
| Simulated network of 20-50 projects | `simulate` makes 39 projects. The organizers provide no data, so the demo runs on our simulation. |

---

## Testing

```bash
pytest -q          # 213 tests, no Ollama or internet needed
```

CI runs the same command on every pull request (Python 3.11). Tests cover the trust formulas and every decision
rule (including the newcomer, brigade and expiry cases), the loaders' validation, the campaign detector and its
thresholds, advisories, the behavior alarm, the lab, the report, and the command-line interface. The model call is
mocked in tests so CI never depends on Ollama; one extra test (`tests/test_ablation.py`) calls the real model and is
skipped when Ollama is not running. The proof that the real model was used is in `examples/`
(`campaigns.json` and `ablation.json` show `embedding_used: true`), and `make_examples.sh` refuses to finish otherwise.

---

## What is not built

- **Vouch-file adapter:** A Ghostty-style `+handle` / `-handle` flat-file format is
  sketched in the design but not implemented in the loader.
- **A drawn trust graph and dark mode:** The HTML report is a searchable explorer (projects, PRs,
  decisions with trust paths, campaigns, lab fixtures). It does not draw a node-link graph and has one
  light theme.
- **Real open-source data:** All networks are simulated or hand-crafted, because no public source
  publishes trust links between projects. The loader reads plain files, so real data could be converted
  to them, but we have not done so.
- **Collusion cap:** The design notes a stretch goal to cap how much two mutually-trusting
  projects can inflate each other's score. Not implemented.
- **Cohort bursts:** many new accounts that each send a single, different PR to a different project are not
  detected. Only one account hitting many projects, or near-identical text, is.
- **Extra lab scenarios:** The lab covers four attacks plus one failing control. Additional
  scenarios (e.g. gradual reputation laundering) are not included.
- **Live GitHub integration:** TrustNet reads files, not GitHub. A GitHub Action or webhook that
  produces the input files is the natural next step; it was not built.
- **Calibrated thresholds:** All numbers in `policy.json` are our own defaults, tuned on our own
  simulation.

---

## Responsible use and AI disclosure

- **Data:** only simulated and hand-made data. TrustNet reads files and never posts comments, issues or labels on real
  projects. No secrets are stored in the repository.
- **Decisions are triage, not verdicts:** nothing is auto-rejected. HOLD sends a PR to a human; a denounce needs
  evidence to count fully and can expire.
- **Runtime model:** `nomic-embed-text` (open-weight), run locally through Ollama. It only supplies a similarity score.
- **AI coding assistants used during development** (declared in each pull request): Claude Code, OpenAI Codex and
  Antigravity. Every team member is expected to explain the code.

---

## Project layout

```
trustnet/             Python package
  models.py           dataclasses: Project, Account, PR, Network, Decision, Campaign
  loaders.py          load_network(path) -> Network, load_policy() -> (policy, hash)
  trust.py            project_trust, evaluate_author, evaluate_pr, naive_score
  advisory.py         build_advisory / load_advisory (campaign advisories)
  similarity.py       TF-IDF + nomic-embed-text cosine similarity (batched, with fallback)
  campaigns.py        text-campaign detector and the text-independent behavior (fan-out) alarm
  ablation.py         same reworded campaign with the model off and on
  fanout_demo.py      demo of the behavior alarm and the vouch override
  lab.py              adversarial lab (naive vs defended, five scenarios)
  simulate.py         seeded network generator
  report.py           offline HTML report (searchable explorer)
  cli.py, __main__.py command-line interface (python -m trustnet)
policy.json           every numeric threshold, with a hash printed in outputs
tests/                213 tests: trust, loaders, models, campaigns, similarity, advisory, ablation,
                      fanout, lab, simulate, report, CLI, and four hand-made fixture networks
docs/
  PLAN.md             build plan, data contract, decision log
  DESIGN.md           every formula and threshold, with the measured calibration table
  DEMO.md             8-minute demo script with fallbacks
  SLIDES.md           presentation outline
  MENTOR_NOTES.md     organizer Q&A (what was and was not answered)
  progress/           one log per team member
examples/             real pipeline input and output, committed from make_examples.sh
.github/              CI workflow (Python 3.11, pip install, pytest -q) and the pull request template
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

---

## License

MIT. See [LICENSE](LICENSE).
