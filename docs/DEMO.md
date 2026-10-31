# TrustNet — 8-Minute Demo Script

Hacktoberfest 2026 Hack Day, Sonipat · Team Sophons · Problem 7

**Presenter:** Run through this top to bottom. Times are targets, not hard stops.
**Fallbacks** are marked 🔴 — if something breaks, jump straight to the fallback.

---

## Before you go up (checklist — do this 15 min before demo)

- [ ] `cd TrustNet && source .venv/bin/activate`
- [ ] `python -m trustnet simulate --projects 30 --seed 42` — confirm it finishes
- [ ] `ollama list` — confirm `nomic-embed-text` is listed
- [ ] Open the HTML report in a browser tab (generated in the step above)
- [ ] Font size in terminal ≥ 18pt, browser zoom ≥ 125%
- [ ] Have `examples/` folder open in a second tab as backup

---

## Segment 1 — Hook (0:00 – 0:45)

**Say:**
> "Imagine you wake up and find 38 identical pull requests have hit 25 of your
> projects in the last two hours. Each maintainer saw only one — but together,
> it's a coordinated spam campaign. How do you stop it without closing the door
> on every new contributor?"

**Action:** Show the terminal. Nothing to run yet — just talk.

---

## Segment 2 — Stakes (0:45 – 1:30)

**Say:**
> "The naive answer is to block anyone with no history. But that punishes
> newcomers who haven't done anything wrong. TrustNet separates the two:
> a newcomer with no record gets PROVISIONAL — a human reviews the PR —
> while a confirmed campaign member gets HOLD. And crucially, every project
> makes its own decision. The same author can get two different answers from
> two different projects. That's decentralization."

---

## Segment 3 — Live run (1:30 – 4:30)

### 3a. Generate the network (1:30 – 2:00)

```bash
python -m trustnet simulate --projects 30 --seed 42
```

**Say:**
> "This seeds a network of 30 projects with trust edges, honest accounts,
> 15 newcomers, and four planted attacks: a spam campaign, a legitimate
> dependency bump, a denounce brigade, and a sybil clique.
> Same seed always gives identical output — fully reproducible."

🔴 **Fallback:** `ls examples/network/` — point to the pre-generated folder.

---

### 3b. Evaluate a newcomer (2:00 – 2:45)

```bash
python -m trustnet evaluate --as proj-01 --pr pr-newcomer-01
```

**Say:**
> "This newcomer has no vouch and no denounce anywhere. Belief is 0,
> disbelief is 0, uncertainty is 1. The decision is PROVISIONAL.
> They are never blocked just for being new."

**Point to output lines:**
```
decision     : PROVISIONAL
belief       : 0.000
disbelief    : 0.000
uncertainty  : 1.000
reasons      : (none — no trust history)
```

🔴 **Fallback:** Show `examples/newcomer_decision.json` in the terminal with `cat`.

---

### 3c. Same author, two projects (2:45 – 3:15)

```bash
python -m trustnet evaluate --as proj-01 --pr pr-alice-07
python -m trustnet evaluate --as proj-14 --pr pr-alice-07
```

**Say:**
> "Same PR, same author, two different answers — because proj-01 and proj-14
> have different trust graphs. This is the decentralization. There is no
> central authority. Each project decides for itself."

🔴 **Fallback:** Show side-by-side cards in the HTML report (already open in browser).

---

### 3d. Brigade ignored (3:15 – 3:45)

```bash
python -m trustnet evaluate --as proj-01 --pr pr-alice-07 --verbose
```

**Say:**
> "Five fake projects denounce this author. Watch the output — every one
> of them is listed as 'ignored: source not trusted'. The decision doesn't
> move. You can't brigade someone by creating fake projects."

**Point to output lines:**
```
ignored:
  - fake-01: ignored: source not trusted
  - fake-02: ignored: source not trusted
  ...
```

🔴 **Fallback:** Show the brigade fixture: `cat tests/fixtures/brigade/labels.json`

---

### 3e. Campaign detection (3:45 – 4:30)

```bash
python -m trustnet campaigns
```

**Say:**
> "The campaign detector found one flagged cluster: 38 PRs, 25 projects,
> 2 hours, 84% of authors with accounts younger than 14 days.
> Score 0.78 — above the 0.6 threshold. Every author in that cluster
> gets HOLD, even if their individual PR looks fine.
> The legitimate dependency bump is not flagged — old account, vouched maintainer."

**Point to:**
```
FLAGGED  score=0.78  38 PRs · 25 projects · 2h03m · 84% young accounts
         embedding_used: true
```

🔴 **Fallback:** `cat examples/campaigns.json` — show the pre-run output.

---

## Segment 4 — Lab results (4:30 – 5:30)

```bash
python -m trustnet lab
```

**Say:**
> "The lab runs four attack scenarios — brigade denounce, sybil clique,
> trust laundering, collusive cluster — and compares the naive baseline
> against our defended system. In every scenario, the attacker gains less
> with TrustNet than with naive counting. False positives on honest
> newcomers stay at zero."

**Point to the Markdown table printed to stdout:**

```
Scenario          | Naive score | Defended | Reduction | FP rate
brigade-denounce  |        0.82 |     0.04 |      95%  |    0%
sybil-clique      |        0.91 |     0.11 |      88%  |    0%
trust-laundering  |        0.74 |     0.18 |      76%  |    0%
collusive-cluster |        0.88 |     0.09 |      90%  |    0%
```

🔴 **Fallback:** Show the lab table in the HTML report (open in browser, scroll to Lab section).

---

## Segment 5 — Model and close (5:30 – 7:00)

### Open the HTML report

```bash
python -m trustnet report
# opens report.html in the browser
```

**Say:**
> "The report shows decision cards, the campaign card with evidence,
> the lab table, and a trust graph where ignored denounces are dashed
> and labelled 'ignored: source not trusted'.
> Works in light and dark mode, readable on a phone."

**Then say:**
> "The model we use is nomic-embed-text — open-weight, runs locally
> through Ollama. It converts PR text into embeddings so we can detect
> reworded spam that keyword filters miss. All trust decisions are
> deterministic rules. The model only supplies a similarity score.
> If Ollama is down, we fall back to TF-IDF and say so in the output —
> you can see 'embedding_used: false' in that case."

> "Tests cover every decision rule, the TF-IDF fallback, the campaign
> detector, and the full lab. CI runs on GitHub Actions with Python 3.11.
> We have not built a web server, live GitHub integration, or a vouch-file
> adapter — those are cut features we documented honestly."

---

## Segment 6 — Buffer / Q&A prep (7:00 – 8:00)

Use this time to switch to the browser report if judges want to see it,
or to run any command a judge asks for. See Q&A cards below.

---

## Judge Q&A cards

| Question | One-line answer | Point to |
|---|---|---|
| If A trusts B and B trusts C, how much does A trust C? | `0.9 × 0.9 × 0.6 = 0.486` — multiply weights, 0.6 decay per hop after the first, max 3 hops | `docs/DESIGN.md §1` |
| How do you stop fake denounces? | Denounces from projects with trust < 0.25 are ignored. You see them listed as "ignored: source not trusted" | Brigade output in terminal |
| What happens to a brand-new contributor? | Belief=0, disbelief=0, uncertainty=1 → PROVISIONAL. Never HOLD just for being new | Newcomer eval output |
| Why not just detect AI-written text? | Reworded spam beats keyword and many classifier approaches. Embeddings catch semantic similarity even when wording changes. But the model only scores similarity — rules decide | `docs/DESIGN.md §4` |
| Where is the decentralization? | Same PR, two projects, two decisions. No central authority. Each project picks who it trusts | 3c output in terminal |
| Which model and why? | `nomic-embed-text` via Ollama — open-weight, local, no API key, falls back to TF-IDF if down | `HACKATHON.md` |
| What about false positives? | Lab shows 0% FP on honest newcomers across all four scenarios. Bulk-bump fixture proves old-account legitimate updates are not flagged | Lab table |
| What if projects collude? | Collusive-cluster scenario in the lab. Mutual vouching is bounded by top-k=3 and the 0.6 hop decay | Lab table, `docs/DESIGN.md §2` |

---

## Fallback ladder (if everything breaks)

1. **Ollama down** → TF-IDF fallback runs automatically; output says `embedding_used: false`. Keep going.
2. **Simulate fails** → `ls examples/network/` and use the pre-generated data.
3. **CLI broken** → Open `examples/report.html` in the browser and walk through it.
4. **Browser broken** → `cat examples/campaigns.json` and `cat examples/lab.json` in the terminal.
5. **Total failure** → Walk through `docs/DESIGN.md` on screen and explain the formulas verbally. The judges are evaluating understanding, not just live output.
