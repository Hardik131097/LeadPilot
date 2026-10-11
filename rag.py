"""
RAG layer: two knowledge bases stored in a Chroma vector store.
  - sales_kb  : product facts, case studies, objection handling  (used by Research + Writer agents)
  - policy_kb : brand voice and compliance policy                 (used by Reviewer agent)

Embeddings are computed locally (hashed TF-IDF style n-gram vectors) so the
system runs offline with no extra model download. If chromadb is not installed,
an in-memory NumPy vector store is used instead with the same interface.
To use semantic embeddings in production, swap `Embedder` for an embedding
model (e.g. Ollama nomic-embed-text or a Hugging Face sentence-transformer)
and Chroma for Pinecone; the agents do not change.
"""
import glob
import os
import re

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer

BASE = os.path.dirname(os.path.abspath(__file__))
KB_DIR = os.path.join(BASE, "knowledge_base")

try:
    import chromadb
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False


# Sales vocabulary: different words people use for the same idea (added after evaluation round 1).
VOCAB = {
    "cost": "price", "costs": "price", "pricing": "price", "priced": "price", "fee": "price", "fees": "price",
    "charge": "price", "charges": "price", "expensive": "price", "cheap": "price", "rs": "price",
    "spreadsheet": "excel", "spreadsheets": "excel", "sheets": "excel",
    "approves": "approval", "approve": "approval", "approved": "approval", "sign": "approval",
    "unsubscribe": "optout", "opt": "optout", "consent": "optout",
    "hospital": "healthcare", "hospitals": "healthcare", "nursing": "healthcare",
    "warehouse": "logistics", "warehouses": "logistics", "courier": "logistics",
    "statistics": "figures", "statistic": "figures", "numbers": "figures", "stats": "figures",
}
STOP = {"a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "is", "are", "be", "it", "its", "we",
        "our", "us", "you", "your", "they", "their", "with", "as", "at", "by", "from", "that", "this", "can",
        "do", "does", "how", "much", "what", "who", "which", "per", "not", "no", "if", "will", "has", "have"}


def stem(word):
    for suffix in ("ations", "ation", "ings", "ing", "ies", "es", "ed", "al", "s"):
        if len(word) > len(suffix) + 3 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def analyze(text):
    words = re.findall(r"[a-z0-9][a-z0-9-]*", text.lower())
    tokens = [stem(VOCAB.get(w, w)) for w in words if w not in STOP]
    return tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]


class Embedder:
    """Local hashed bag-of-words vectors with stemming and a small sales vocabulary.
    Lexical, not semantic: it runs offline with no model download (see report, Limitations)."""

    def __init__(self, dims=4096):
        self.vec = HashingVectorizer(n_features=dims, alternate_sign=False, norm="l2", analyzer=analyze)

    def __call__(self, texts):
        return self.vec.transform(texts).toarray()


def chunk_markdown(path):
    """Split a markdown file into one chunk per '## ' section."""
    text = open(path, encoding="utf-8").read()
    source = os.path.basename(path)
    chunks = []
    for part in re.split(r"\n(?=## )", text):
        lines = part.strip().splitlines()
        if not lines or not lines[0].startswith("## "):
            continue
        section = lines[0][3:].strip()
        body = " ".join(l.strip() for l in lines[1:] if l.strip())
        industry = re.search(r"Industry:\s*([A-Za-z ]+?)\.", body)
        chunks.append({"text": f"{section}. {body}", "source": source, "section": section,
                       "industry": industry.group(1).strip() if industry else ""})
    return chunks


class KnowledgeBase:
    def __init__(self, name, folder, embedder):
        self.name, self.embed = name, embedder
        self.chunks = []
        for path in sorted(glob.glob(os.path.join(KB_DIR, folder, "*.md"))):
            self.chunks += chunk_markdown(path)
        vectors = self.embed([c["text"] for c in self.chunks])
        self.backend = "Chroma" if HAS_CHROMA else "NumPy (fallback)"
        if HAS_CHROMA:
            client = chromadb.EphemeralClient()
            try:
                client.delete_collection(name)
            except Exception:
                pass
            self.col = client.create_collection(name, embedding_function=None,
                                                metadata={"hnsw:space": "cosine"})
            self.col.add(ids=[f"{name}-{i}" for i in range(len(self.chunks))],
                         embeddings=vectors.tolist(),
                         documents=[c["text"] for c in self.chunks],
                         metadatas=[{k: c[k] for k in ("source", "section", "industry")} for c in self.chunks])
        else:
            self.matrix = vectors

    def search(self, query, k=2, industry=None):
        """Return the top-k chunks for a query, optionally filtered by industry metadata."""
        q = self.embed([query])[0]
        if HAS_CHROMA:
            where = {"industry": industry} if industry else None
            if where and not any(c["industry"] == industry for c in self.chunks):
                where = None
            res = self.col.query(query_embeddings=[q.tolist()], n_results=min(k, len(self.chunks)), where=where)
            return [{"text": d, **m, "score": round(1 - dist, 3)}
                    for d, m, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])]
        scores = self.matrix @ q
        idx = [i for i in np.argsort(-scores)
               if not industry or self.chunks[i]["industry"] == industry
               or not any(c["industry"] == industry for c in self.chunks)][:k]
        return [{**self.chunks[i], "score": round(float(scores[i]), 3)} for i in idx]

    def all_text(self):
        return " ".join(c["text"] for c in self.chunks)


_CACHE = {}


def get_kbs():
    """Build both knowledge bases once and reuse them."""
    if not _CACHE:
        emb = Embedder()
        _CACHE["sales"] = KnowledgeBase("sales_kb", "sales", emb)
        _CACHE["policy"] = KnowledgeBase("policy_kb", "policy", emb)
    return _CACHE["sales"], _CACHE["policy"]
