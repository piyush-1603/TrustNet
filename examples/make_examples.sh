#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/.." && pwd)"

# Select Python environment (.venv python if present, else python3, else python)
if [ -f "$ROOT/.venv/bin/python" ]; then
    PY="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
else
    PY="python"
fi

# The examples must come from the real model: Ollama running with nomic-embed-text pulled.
if ! curl -s -m 2 http://localhost:11434/api/tags >/dev/null 2>&1; then
    if command -v ollama >/dev/null 2>&1; then
        echo "==> Starting local Ollama server..."
        ollama serve >/dev/null 2>&1 &
        SERVER_PID=$!
        sleep 3
    else
        echo "ERROR: Ollama is not installed. Install it from https://ollama.com, then run: ollama pull nomic-embed-text" >&2
        exit 1
    fi
fi
if ! curl -s -m 5 http://localhost:11434/api/tags | grep -q '"nomic-embed-text'; then
    echo "ERROR: model nomic-embed-text is not installed. Run: ollama pull nomic-embed-text" >&2
    exit 1
fi

echo "==> 1. Generating simulated network (seed=42, 30 projects)..."
$PY -m trustnet simulate --projects 30 --seed 42 --out "$DIR/network"

echo "==> 2. Running campaign detector with embeddings..."
$PY -m trustnet campaigns --network "$DIR/network" --json > "$DIR/campaigns.json"

# Verify that embedding_used is true
EMB_USED=$($PY -c "import json; data=json.load(open('$DIR/campaigns.json')); print(any(c.get('embedding_used') for c in data))")
if [ "$EMB_USED" != "True" ]; then
    echo "ERROR: embedding_used is false! Ollama with nomic-embed-text must be running." >&2
    exit 1
fi
echo "    [verified] embedding_used is true (nomic-embed-text)"

echo "==> 2b. Publishing proj-01's campaign advisory, and proj-02 importing it..."
$PY -m trustnet advisory --as proj-01 --network "$DIR/network" --out "$DIR/advisory.json"
$PY -m trustnet evaluate --as proj-02 --pr pr-151 --network "$DIR/network" --no-local-detection --advisory "$DIR/advisory.json" --json > "$DIR/evaluate_with_advisory.json"

echo "==> 2c. Evaluating a newcomer's PR (pr-203) as proj-01..."
$PY -m trustnet evaluate --as proj-01 --pr pr-203 --network "$DIR/network" --json > "$DIR/evaluate_newcomer.json"

echo "==> 3. Evaluating sample PR pr-001 as proj-01..."
$PY -m trustnet evaluate --as proj-01 --pr pr-001 --network "$DIR/network" --json > "$DIR/evaluate.json"

echo "==> 4. Running adversarial attack lab..."
$PY -m trustnet lab --json > "$DIR/lab.json"

echo "==> 5. Generating HTML report..."
$PY -m trustnet report --network "$DIR/network" --out "$DIR/report.html"

echo "==> All example artifacts successfully generated in examples/."
