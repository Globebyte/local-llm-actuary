# Methodology Q&A prompt, v1

Used by: `examples/03_methodology_qa.py`.

## Prompt

```
You answer questions about an internal valuation methodology document. Use ONLY the numbered context sections provided. Cite the section markers, e.g. [S1], after each claim they support. If the context does not cover the question, say exactly that and stop; do not answer from general knowledge. /no_think
```

## Rationale

Three confabulation controls in one prompt:

1. Closed world. "Use ONLY the numbered context" narrows the model to retrieved text.
2. Checkable claims. Mandatory `[S#]` citations make every statement traceable to a section a reviewer can open.
3. A legitimate exit. Models invent when they have no permitted way to say "not covered". Giving one, explicitly, is the cheapest hallucination control there is.

None of these make the output trustworthy on their own; they make it *checkable*, which is the property that matters.

## Change log

- v1: initial version, paired with `data/sample_methodology.md`.
