"""03: Question answering over your own methodology documents (life/health).

Local retrieval-augmented generation in ~150 lines, no framework:

    1. Chunk the document by markdown heading.
    2. Embed the chunks with a local embedding model (never leaves the machine).
    3. Retrieve the most relevant sections for the question.
    4. Require the model to answer only from the retrieved text, cite section
       numbers, and say plainly when the document does not cover the question.

Step 4 is the confabulation control: retrieval narrows what the model can
draw on, the citation requirement makes the answer checkable, and the
refusal instruction gives it a legitimate exit instead of an invented one.

Prerequisites:
    ollama pull qwen3:8b
    ollama pull nomic-embed-text

Run:
    python examples/03_methodology_qa.py "How is the credibility factor set?"
    python examples/03_methodology_qa.py --dry-run     # chunking only, no server
"""

import argparse
import math
import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
TOP_K = 4


def chunk_by_heading(markdown: str) -> list[dict]:
    """Split a markdown document into sections keyed by their headings.

    Heading-based chunks keep each retrieved passage self-contained and give
    the model a natural citation unit. For longer documents, split oversized
    sections further (e.g. by paragraph, ~300-500 words per chunk).
    """
    sections, current = [], {"heading": "Preamble", "text": ""}
    for line in markdown.splitlines():
        if line.startswith("#"):
            if current["text"].strip():
                sections.append(current)
            current = {"heading": line.lstrip("# ").strip(), "text": ""}
        else:
            current["text"] += line + "\n"
    if current["text"].strip():
        sections.append(current)
    return [s for s in sections if len(s["text"].strip()) > 40]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?",
                    default="How is the credibility factor for mortality set?")
    ap.add_argument("--dry-run", action="store_true",
                    help="show the chunking and exit (no model calls)")
    args = ap.parse_args()

    doc = (REPO / "data" / "sample_methodology.md").read_text(encoding="utf-8")
    chunks = chunk_by_heading(doc)

    if args.dry_run:
        print(f"{len(chunks)} chunks:")
        for i, c in enumerate(chunks, 1):
            print(f"  [S{i}] {c['heading']} ({len(c['text'].split())} words)")
        return

    from openai import OpenAI
    client = OpenAI(base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
                    api_key="ollama")
    model = os.getenv("LLM_MODEL", "qwen3:8b")

    # Embed corpus and question locally. For a document this size, embedding
    # on every run is fine; for a document library, cache embeddings to disk.
    corpus = client.embeddings.create(
        model=EMBED_MODEL, input=[c["text"] for c in chunks])
    q_emb = client.embeddings.create(
        model=EMBED_MODEL, input=[args.question]).data[0].embedding

    scored = sorted(
        ((cosine(q_emb, d.embedding), i) for i, d in enumerate(corpus.data)),
        reverse=True)
    picked = [i for _, i in scored[:TOP_K]]

    context = "\n\n".join(
        f"[S{j + 1}] {chunks[i]['heading']}\n{chunks[i]['text'].strip()}"
        for j, i in enumerate(picked))

    system = (
        "You answer questions about an internal valuation methodology "
        "document. Use ONLY the numbered context sections provided. Cite the "
        "section markers, e.g. [S1], after each claim they support. If the "
        "context does not cover the question, say exactly that and stop; do "
        "not answer from general knowledge. /no_think"
    )
    user = f"Context:\n{context}\n\nQuestion: {args.question}"

    response = client.chat.completions.create(
        model=model, temperature=0, seed=42,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}],
    )

    print(f"Q: {args.question}\n")
    print(strip_think(response.choices[0].message.content))
    print("\nRetrieved sections:")
    for j, i in enumerate(picked, 1):
        print(f"  [S{j}] {chunks[i]['heading']}")


if __name__ == "__main__":
    sys.exit(main())
