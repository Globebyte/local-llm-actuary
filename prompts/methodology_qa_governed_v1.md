# Methodology Q&A prompt, governed variant, v1

Used by: `examples/04_governance_wrapper.py`, recorded in each audit record as `prompt.template_id = "methodology-qa"`, `prompt.template_version = "1.0.0"`.

## Prompt

```
You answer questions about an internal valuation methodology document, using ONLY the numbered sections supplied. Reply with a single JSON object and nothing else, with exactly these keys: "answer" (string), "citations" (array of section identifiers such as "S3" that support the answer), and "not_covered" (boolean, true if the sections do not address the question). If not_covered is true, leave citations empty and do not answer from general knowledge. /no_think
```

## Rationale

This is the structured-output sibling of [`methodology_qa_v1.md`](methodology_qa_v1.md). Same three confabulation controls (closed world, mandatory citations, a legitimate exit), with the output contract changed from prose to JSON so that the citations can be checked by code rather than by a reader.

- JSON, not prose. Free text containing "as set out in section 3" gives a validator nothing to work with. A `citations` array can be resolved against the sections actually supplied, and an unresolvable identifier becomes a caught error rather than a plausible-looking sentence.
- `not_covered` as an explicit boolean. In the prose version the refusal is detected by reading the answer. Here it is a field, so "the document does not cover this" is a machine-readable outcome that passes validation rather than an anomaly.
- Citations required when answering. The validator treats an answer with an empty `citations` array as invalid. The prompt and the validator have to agree on this, or the contract is decorative.
- `/no_think`. Disables Qwen3's reasoning block. A `<think>` block wrapped around a JSON object breaks the parse, so this matters more here than in the prose variant.

Tested on `qwen3:8b` via Ollama's OpenAI-compatible endpoint with `response_format={"type": "json_object"}`. The model reliably returns parseable JSON under that setting but does not always return bare identifiers: `"S4: Mortality assumptions"` occurs in place of `"S4"`, so the validator extracts the identifier with a regular expression rather than rejecting the response. Shape variance is tolerated; an unresolvable citation never is.

## Change log

- v1: initial version, paired with `governance/use_case.json` v1.0.0 and `data/sample_methodology.md`.
