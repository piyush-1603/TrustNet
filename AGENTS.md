# Instructions for AI assistants and teammates

You may have no memory of earlier work. Do this first, every session:

1. `git pull` on `main`, then read `docs/PLAN.md` (plan, contract, build order, decision log).
2. Read your own progress file in `docs/progress/` (listed in PLAN.md under "Who owns what").
3. Run `git log --oneline -15` and `pytest -q` to see the real state. Trust the code and tests over any note.

## Commands

```bash
python3.11 -m venv .venv && source .venv/bin/activate    # once
pip install -r requirements.txt                          # CI does exactly this
pytest -q                                                # CI does exactly this
python -m trustnet <command>                             # CLI, once cli.py and __main__.py exist
```

CI runs on Python 3.11. If it passes locally on another Python but fails in CI, CI is right.

## How to ship a change (you do this yourself, no need to ask anyone)

```bash
git checkout main && git pull
git checkout -b <pN>/<short-topic>        # e.g. p2/campaign-detector
# ... edit your files, write tests, run pytest -q ...
# add one log line to YOUR progress file (docs/progress/pN-name.md)
git add -A && git commit -m "campaigns: cluster near-duplicate PRs"
git push -u origin <pN>/<short-topic>
gh pr create --fill                        # then fill all four template sections truthfully
```

Merge only after CI is green and someone other than the author has looked at it. Never commit to `main`. Never force-push `main`.

## Rules

- Edit only the files you own (see PLAN.md). Need a change in someone else's file? Ask them in chat, or open a small PR they review.
- Do not rename files, functions or data fields from the contract in `docs/PLAN.md`. Others import them. If the contract must change, tell Shaurya first and update PLAN.md in the same PR.
- Every PR adds one log entry to **your own** progress file only. Do not edit anyone else's progress file; that keeps PRs from conflicting. Only Shaurya edits the PLAN.md status table and decision log.
- Write tests with the code. CI must be green before merge. Tests must not need Ollama, internet, or secrets.
- The PR description fills the template honestly: which models the code uses in this PR (`none` is a valid answer), which AI coding assistants helped, how it was tested.
- Claim `nomic-embed-text` only where the code really calls it. No secrets in git. Public or simulated data only. Never post comments or issues on real projects.
- Keep code short and readable. Every member must be able to explain it to a judge.
- Do not leave stubs that pretend to work. If something is not done, say so in your progress file.
