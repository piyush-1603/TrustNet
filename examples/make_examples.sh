#!/usr/bin/env bash
set -e

# Use python if available, otherwise python3
if command -v python >/dev/null 2>&1; then
    PY="python"
else
    PY="python3"
fi

echo "==> Generating simulated network (seed=42, 30 projects)..."
$PY -m trustnet simulate --projects 30 --seed 42 --out examples/network

echo "==> Running campaign detector..."
$PY -m trustnet campaigns --network examples/network --json > examples/campaigns.json

echo "==> Evaluating sample PR pr-001 as proj-01..."
$PY -m trustnet evaluate --as proj-01 --pr pr-001 --network examples/network --json > examples/evaluate.json

echo "==> Generating HTML report..."
$PY -m trustnet report --network examples/network --out examples/report.html

echo "==> All examples successfully generated in examples/."
