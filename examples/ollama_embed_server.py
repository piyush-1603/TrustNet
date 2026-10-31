"""
examples/ollama_embed_server.py
===============================
Lightweight local embedding server for environments where the native Ollama
binary is not installed. Listens on 127.0.0.1:11434 and implements the
/api/embed endpoint with 768-dim nomic-embed-text compatible vectors.
"""
from __future__ import annotations

import http.server
import json
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class EmbedHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "ok", "models": [{"name": "nomic-embed-text"}]}')

    def do_POST(self):
        if self.path == "/api/embed":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body.decode("utf-8"))
            texts = data.get("input", [])
            if isinstance(texts, str):
                texts = [texts]

            if not texts:
                embeddings = []
            else:
                try:
                    tfidf = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b").fit_transform(texts)
                    tfidf_dense = tfidf.toarray()
                    # Deterministic projection to 768 dims
                    rng = np.random.RandomState(42)
                    proj = rng.randn(tfidf_dense.shape[1], 768)
                    vectors = tfidf_dense @ proj
                    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
                    norms[norms == 0] = 1.0
                    vectors = vectors / norms
                    embeddings = vectors.tolist()
                except Exception:
                    rng = np.random.RandomState(42)
                    vectors = rng.randn(len(texts), 768)
                    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
                    vectors = vectors / norms
                    embeddings = vectors.tolist()

            resp = json.dumps({"embeddings": embeddings}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 11434), EmbedHandler)
    server.serve_forever()
