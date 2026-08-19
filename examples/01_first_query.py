"""01: First query against a local model.

The single most useful fact in this repository: Ollama exposes an
OpenAI-compatible API on localhost. The Python you already write against a
cloud endpoint runs unchanged against your own machine. Change the base URL;
keep everything else.

Prerequisites (see 00_install.md):
    ollama pull qwen3:8b
    pip install -r requirements.txt

Run:
    python examples/01_first_query.py
"""

import os
import re

from openai import OpenAI

# Point the standard OpenAI client at the local Ollama server. The api_key is
# required by the client library but ignored by Ollama; any string works.
client = OpenAI(base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
                api_key="ollama")

MODEL = os.getenv("LLM_MODEL", "qwen3:8b")


def strip_think(text: str) -> str:
    """Qwen3 is a hybrid reasoning model and may emit <think> blocks.

    For deterministic, parseable output we disable thinking with the
    /no_think soft switch in the system prompt and strip any residual
    block defensively. Other model families are unaffected.
    """
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def main() -> None:
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,          # deterministic-leaning settings...
        seed=42,                # ...reduce variation; they do not eliminate it.
        messages=[
            {"role": "system",
             "content": "You are a concise assistant for actuarial analysts. /no_think"},
            {"role": "user",
             "content": "Explain IBNR in three sentences for a new analyst."},
        ],
    )
    print(f"[model: {MODEL}]\n")
    print(strip_think(response.choices[0].message.content))


if __name__ == "__main__":
    main()
