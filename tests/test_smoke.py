from pathlib import Path

import trustnet

ROOT = Path(__file__).resolve().parents[1]


def test_package_imports():
    assert trustnet.__doc__


def test_pr_template_keeps_the_four_required_sections():
    text = (ROOT / ".github" / "pull_request_template.md").read_text()
    for heading in (
        "## What this PR does",
        "## Models the product uses in this PR",
        "## AI coding assistants that helped write it",
        "## How we tested it",
    ):
        assert heading in text
