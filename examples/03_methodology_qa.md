# Example 03: retrieval over your own documents, and the confabulation problem

Script: [`03_methodology_qa.py`](03_methodology_qa.py) · Practice area: life / health · Run: `python examples/03_methodology_qa.py "How is the credibility factor set?"`

## The task, in actuarial terms

A valuation methodology document runs to tens of pages: data sources and validation, mortality and lapse bases, expense allocation, discount rates, the projection approach, controls, limitations. Questions about it arrive constantly: from a reviewing actuary, an auditor, a new joiner, a regulator. Answering them means knowing which section says what, and the person who knows is usually busy.

This is a good task for a language model and a *terrible* one for a language model used naively. The document is confidential, so it cannot be pasted into a public chat interface. And a model asked about your methodology from general knowledge will answer from the average of every actuarial document on the internet, fluently and wrongly. Both problems have solutions, and this example is the smaller of the two: retrieval for the second, local execution for the first.

## The architecture, in four steps

The script is about 150 lines with no framework, which is deliberate: retrieval-augmented generation is often presented as something requiring a stack, and at this scale it does not.

1. Chunk the document by heading. [`chunk_by_heading()`](03_methodology_qa.py#L36-L53) walks the markdown, starting a new section at each `#` line. The 8.5 KB methodology document yields 11 citable sections.

Headings are a good chunking boundary for actuarial documents specifically. A section on mortality assumptions is a coherent unit of meaning that a reviewer can open and check, and a citation to it is intelligible to a human. Chunking by fixed token count, the default in most tutorials, cuts mid-sentence, splits a table from its caption, and produces citations no reviewer can act on. The docstring notes the limit: for longer documents you must split oversized sections further, because a section that runs to several pages both dilutes retrieval and stops being a useful citation. Roughly 300 to 500 words per chunk is the usual compromise.

Sections under 40 characters are dropped, which removes heading-only lines that would otherwise retrieve on their title and supply no content.

2. Embed every chunk locally. An embedding turns text into a vector of numbers positioned so that passages about similar things sit near each other. `nomic-embed-text` produces 768 dimensions per passage and runs entirely on your machine, which matters: an embedding model is still a model receiving your confidential text.

3. Retrieve the nearest sections to the question. The question is embedded the same way, and cosine similarity ranks the chunks:

```python
def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0
```

For an actuary, the useful reading of cosine similarity is that it measures the *angle* between two vectors and ignores their length: it asks whether two passages point in the same direction in meaning-space, not how emphatically. It runs from −1 to 1, and in practice on text embeddings you will see values clustered well above zero.

A detail worth knowing: `nomic-embed-text` returns vectors already normalised to unit length (I measured an L2 norm of exactly 1.0), so the two square roots in that function both evaluate to 1 and the calculation reduces to the plain dot product. The normalisation is defensive rather than necessary here, which is the right way to write it, since a different embedding model makes no such promise.

`TOP_K = 4` sections are supplied to the model. That number is a genuine trade-off: too few and the answer-bearing section may not be retrieved at all; too many and the relevant passage is diluted among irrelevant ones while the prompt grows and the call slows. Four is reasonable for an 11-section document and would be far too few for a corpus of a thousand.

4. Answer under three constraints. The retrieved sections are labelled `[S1]` to `[S4]` and passed with the question under a system prompt carrying three separate controls, recorded in [`prompts/methodology_qa_v1.md`](../prompts/methodology_qa_v1.md).

## The three confabulation controls

Confabulation, NIST's term for what is loosely called hallucination, is the production of confidently stated, well-formed, false content. It is the dominant risk in actuarial use of language models, for a reason worth stating plainly: a confabulated answer looks exactly like a correct one. The grammar is right, the register is professional, the internal logic is consistent, and the substance is invented. There is no surface cue to catch.

The prompt applies three controls that do not eliminate it but make it *detectable*, which is the achievable goal.

Closed world. *"Use ONLY the numbered context sections provided."* This narrows the model from everything it has ever read to eleven paragraphs you control. It does not bind the model (an instruction is not a constraint), but it substantially reduces the space in which invention happens.

Mandatory citations. *"Cite the section markers, e.g. [S1], after each claim they support."* This line does more work than any other in the file, because it changes the reviewer's job. Verifying an uncited answer means asking "is this true?", which requires knowing the document. Verifying a cited answer means asking "does [S4] actually say this?", which requires only opening [S4]. The second question is faster, more reliable, and delegable. And confabulation surfaces directly under it: a fabricated claim will carry no citation, or a citation to a section that does not exist, or a citation to a real section that does not support it.

A legitimate exit. *"If the context does not cover the question, say exactly that and stop; do not answer from general knowledge."* This is the control people leave out, and it is close to free. Models invent most readily when they have no permitted way to decline. Giving an explicit, sanctioned way to say "not covered" converts a confabulation into a refusal.

You can watch the third control work. Ask about something the document genuinely does not address:

```bash
python examples/03_methodology_qa.py "What is the reinsurance retention limit?"
```

The methodology document covers purpose, data, mortality, lapse, expenses, discount rates, projection, controls, limitations and version history. It says nothing about reinsurance, and the model says so rather than inventing a figure.

## Reading the output

Two parts, and the second is the one that matters:

```
[answer, with [S1]-style citations inline]

Retrieved sections:
  [S1] 3. Mortality assumptions
  [S2] 9. Limitations and sensitivities
  ...
```

The retrieved-sections list is the audit surface. It tells you what the model was given, which lets you distinguish the two failure modes that look identical from the answer alone:

- A retrieval failure. The right section was never retrieved, so the model could not have answered correctly. The fix is in chunking, the embedding model, or `TOP_K`, not in the prompt.
- A generation failure. The right section was retrieved and the model still got it wrong. The fix is in the prompt, or the model is too small for the task.

Without the retrieved list you cannot tell these apart, and you will spend your time tuning the wrong half of the system. This is why the list is printed rather than logged quietly.

## Known limits

Retrieval failure is silent. This is the most important limitation. If the answer-bearing section is not in the top four, the model works from what it did receive and may produce a confident answer grounded in the wrong passage, with a citation, which makes it look *more* trustworthy, not less. The citation is honest about which section was used; it cannot tell you that a better section existed and was missed.

No reranking. A production system usually retrieves generously (twenty or more chunks), then reranks with a cross-encoder that scores each chunk against the question directly, and passes only the best few. That two-stage approach is materially better than single-stage nearest-neighbour, and it is the first upgrade worth making.

The embedding model is a pinned dependency. Change it and every stored vector must be recomputed, because vectors from different models are not comparable. Version-pin it exactly as you would the generating model. [Example 04](04_governance_wrapper.md) shows why by pinning the model digest.

Citations are section-level, not span-level. `[S4]` points at a whole section. A reviewer still reads the section to find the sentence. Span-level citation is better and needs finer chunking plus character offsets carried through.

Embeddings are recomputed on every run. Fine for one 8.5 KB document, hopeless for a library. Cache them keyed by document hash and embedding-model version, and recompute only what changed.

Cosine similarity is lexically naive in places. Two passages using different vocabulary for the same concept ("lapse" and "surrender", "discount rate" and "valuation interest rate") may sit further apart than you expect. Domain synonyms are a real source of retrieval misses in actuarial corpora, and worth testing for explicitly.

## Taking this to real documents

Version-control the corpus. When the methodology is updated, the corpus must be updated, and every answer should be attributable to a corpus version. An answer that was right against the 2025 basis and is quoted in 2027 is a governance failure with no technical symptom.

Decide what belongs in the corpus. The document set determines answer quality more than the model does. A corpus of current, authoritative, version-stamped documents produces good answers from a mediocre model; a corpus of mixed drafts produces confident nonsense from an excellent one.

Watch what the corpus contains. Local execution means confidential documents can go in, and that is the point. It also means anything in the corpus can surface in an answer, so a corpus containing personal data is a system processing personal data, whatever the retrieval layer does.

Keep the human gate. Every control here makes output *checkable*. None makes it trustworthy. The reviewing actuary remains responsible, and "the model told me" has never been a defence.

## Things to try

- Set `TOP_K = 1` and ask a question spanning two sections, mortality and its limitations, say. Watch a partial answer emerge with a correct citation, which is the clearest demonstration of silent retrieval failure available.
- Ask a question using vocabulary the document does not use, then check the retrieved sections. This is how synonym-driven retrieval misses look from the outside.
- Run `--dry-run` to see the chunking alone. If a section is much larger than its neighbours, it is a candidate for splitting and a likely source of dilution.
- Delete the "if the context does not cover the question" sentence and re-ask about reinsurance retention. The model will invent a limit, in the register of the surrounding document. Keep the output; it is the most persuasive artefact you will have when explaining confabulation to a colleague who has not seen it.
