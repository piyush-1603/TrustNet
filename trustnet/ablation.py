"""Does the model do real work? Run one heavily reworded spam campaign with the model off and on.

The 12 spam PRs say the same thing ("I added a link to my project in your README, please merge") in
12 different wordings, from 12 new accounts to 12 projects within two hours. Keyword matching sees
almost no shared words, so it cannot link them. The embedding model sees the shared meaning.
The 30 background PRs are ordinary changes from old accounts and must stay unflagged.
"""

from datetime import datetime, timedelta, timezone

from .campaigns import detect
from .models import Account, Network, PR, Project

NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)

SPAM = [  # (title, body): one intent, twelve wordings
    ("Add my library to the README", "I built a helpful library and added a link to it in your README. Please review and merge."),
    ("Link to useful tool", "Added a reference to a handy tool I maintain in the readme so users can find it. Kindly merge."),
    ("Update README with resource", "Included a pointer to a resource I created in the project readme; would be great if you could accept."),
    ("README: new resource link", "This adds a link to my open-source package at the end of the readme. Thanks for merging."),
    ("Mention my package in docs", "Put a mention of the package I develop into the documentation. Looking forward to the merge."),
    ("Add helpful link", "I have inserted a link pointing to my project in your readme file, please approve it."),
    ("Promote related tool", "Documentation now references a related tool that I wrote. Please merge this when convenient."),
    ("Add reference to my repo", "Appended a reference to my repository in the readme, I think readers will benefit. Kindly accept."),
    ("Extend README with my project", "This change extends the readme with a short note and link about my project. Please merge."),
    ("Useful link for users", "Added a link that should help users find a related library I maintain. Merge if you agree."),
    ("README improvement: related project", "A related project of mine is now linked from the readme. Requesting a merge."),
    ("Add tool to resources section", "Added my tool to the resources section of the readme with a link. Thank you for merging."),
]

HONEST = [  # (title, body, file): ordinary, varied changes
    ("Fix typo in README", "Corrected 'recieve' to 'receive' in the installation section.", "README.md"),
    ("Bump requests from 2.31 to 2.32", "Routine dependency update; test suite passes locally.", "requirements.txt"),
    ("Add retry with backoff to HTTP client", "Network calls now retry three times with exponential backoff and jitter. Adds unit tests.", "src/http.py"),
    ("Fix off-by-one in pagination", "The last page was skipped when total items were an exact multiple of page size.", "src/pagination.py"),
    ("Handle unicode filenames on Windows", "Paths containing non-ASCII characters crashed the loader; now normalised to NFC.", "src/loader.py"),
    ("Add CI job for Python 3.12", "Extends the test matrix and updates the badge in the README.", ".github/ci.yml"),
    ("Speed up startup by lazy-loading plugins", "Import time dropped from 900ms to 310ms by deferring optional plugin imports.", "src/startup.py"),
    ("Document environment variables", "Adds a table of supported env vars with defaults to docs/configuration.md.", "docs/config.md"),
    ("Refactor config parser", "Splits the 400 line parse() into small functions. No behaviour change.", "src/config.py"),
    ("Add dark mode to settings page", "New toggle stored in localStorage, respects prefers-color-scheme.", "ui/settings.js"),
    ("Fix memory leak in websocket handler", "Listeners were never removed on disconnect, which kept sockets alive.", "src/ws.py"),
    ("Improve error message for missing API key", "Now names the environment variable and links to the setup guide.", "src/errors.py"),
    ("Add Spanish translation", "Translated the UI strings and the onboarding screens into Spanish.", "i18n/es.json"),
    ("Update contributing guide with test instructions", "Explains how to run the suite and how to add a fixture.", "docs/contributing.md"),
    ("Fix broken link in documentation", "The link to the API reference returned 404 after the site move.", "docs/api.md"),
    ("Replace deprecated datetime.utcnow()", "Uses timezone-aware datetime.now(UTC) throughout.", "src/dates.py"),
    ("Add missing type hints to utils", "Fully annotates the helper module; mypy now passes in strict mode.", "src/utils.py"),
    ("Fix crash when config file is empty", "An empty YAML file produced None and raised AttributeError.", "src/cfg.py"),
    ("Improve README examples", "Adds a quick start with a runnable example and expected output.", "README.md"),
    ("Cache DNS lookups", "Adds a small TTL cache to avoid repeated resolver calls in tight loops.", "src/dns.py"),
    ("Fix flaky test in scheduler", "The test depended on wall-clock time; now uses a fake clock.", "tests/test_sched.py"),
    ("Fix grammar in docs", "Several sentences in the tutorial had subject-verb agreement errors.", "docs/tutorial.md"),
    ("Update dependencies in lockfile", "Regenerated package-lock.json with npm 10.", "package-lock.json"),
    ("Add pre-commit hooks", "Runs black, isort and flake8 before each commit.", ".pre-commit.yaml"),
    ("Clarify license header", "Adds SPDX identifiers to every source file.", "LICENSE"),
    ("Fix race condition in cache invalidation", "Two writers could invalidate the same key; guarded with a lock.", "src/cache.py"),
    ("Add tests for date parsing", "Covers leap days, DST changes and invalid inputs.", "tests/test_dates.py"),
    ("Fix typos in docs", "Fixed a few spelling mistakes in the contributing guide.", "docs/guide.md"),
    ("docs: correct spelling in CHANGELOG", "Two words were misspelled in the 2.1 release notes.", "CHANGELOG.md"),
    ("Add FAQ entry about proxies", "Explains how to set HTTPS_PROXY and when it is ignored.", "docs/faq.md"),
]


def _diff(path, line):
    return f"--- a/{path}\n+++ b/{path}\n@@ -1,3 +1,3 @@\n-old line\n+{line}\n"


def build_network():
    """12 projects, 12 new accounts sending reworded spam, 30 old accounts sending ordinary PRs."""
    projects = {f"proj-{i + 1:02d}": Project(id=f"proj-{i + 1:02d}", name=f"proj-{i + 1:02d}") for i in range(12)}
    accounts, prs = {}, []
    for i, (title, body) in enumerate(SPAM):
        handle = f"fresh-{i:02d}"
        accounts[handle] = Account(handle=handle, created_at=(NOW - timedelta(days=3)).isoformat())
        prs.append(PR(id=f"spam-{i:02d}", project=f"proj-{i + 1:02d}", author=handle,
                      created_at=(NOW + timedelta(minutes=9 * i)).isoformat(), title=title, body=body,
                      diff_text=_diff("README.md", f"- [tool](https://example.test/tool-{i})")))
    for i, (title, body, path) in enumerate(HONEST):
        handle = f"regular-{i:02d}"
        accounts[handle] = Account(handle=handle, created_at=(NOW - timedelta(days=400 + 7 * i)).isoformat())
        prs.append(PR(id=f"honest-{i:02d}", project=f"proj-{i % 12 + 1:02d}", author=handle,
                      created_at=(NOW + timedelta(minutes=13 * i)).isoformat(), title=title, body=body,
                      diff_text=_diff(path, "changed line")))
    return Network(projects=projects, accounts=accounts, prs=prs)


def _summarise(campaigns):
    flagged = [c for c in campaigns if c.flagged]
    return {"flagged": bool(flagged),
            "pr_ids": sorted(pr_id for c in flagged for pr_id in c.pr_ids),
            "embedding_used": any(c.embedding_used for c in campaigns)}


def run():
    """Detect the campaign with keyword matching only, then with the model.

    `model_available` is False when Ollama or the model could not be reached; then `model_on` is not
    a model result and must not be presented as one.
    """
    net = build_network()
    off = _summarise(detect(net, use_embeddings=False))
    on = detect(net, use_embeddings=True)
    from .similarity import similarity_matrices
    from .campaigns import pr_text
    available = similarity_matrices([pr_text(net.prs[0])], True)[1] is not None
    return {"spam_prs": len(SPAM), "honest_prs": len(HONEST), "model_available": available,
            "model_off": off, "model_on": _summarise(on) if available else None,
            "spam_ids_found_with_model": (sorted(set(_summarise(on)["pr_ids"]) & {f"spam-{i:02d}" for i in range(len(SPAM))})
                                          if available else []),
            "honest_flagged_with_model": ([p for p in _summarise(on)["pr_ids"] if p.startswith("honest-")]
                                          if available else [])}
