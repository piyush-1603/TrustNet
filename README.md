# TrustNet

A decentralized trust network for open-source contributions (Hacktoberfest 2026 Hack Day Sonipat, Problem 7, team Sophons).

Projects publish vouch and denounce lists and choose which other projects they trust. TrustNet decides, from each project's own point of view, whether to accept a contributor, put them in a provisional review queue, or hold their pull request. It also detects coordinated spam campaigns that hit many projects at once. A contributor with no history is unknown, never auto-rejected.

> Work in progress. The full README (install, usage, design answers, what is not built) lands before the freeze.

## Install and test

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Team workflow

Read [AGENTS.md](AGENTS.md) and [docs/PLAN.md](docs/PLAN.md) before changing anything. All changes go through pull requests.

## License

MIT, see [LICENSE](LICENSE).
