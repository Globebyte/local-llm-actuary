# Governance artefacts

Running the model locally solves the channel problem: confidential material stays on hardware you control. It does not solve the governance problem. You still need to show, later, what was asked, what came back, with which model build, under which settings, who was accountable, and how well it performed. These artefacts are the minimum viable version of that evidence.

The distinction worth holding onto is between a system that *logs* and a system that can *refuse*. A log is written after the fact and asserts what happened. A control is consulted before the fact and can stop the call. `examples/04_governance_wrapper.py` does both, and the declaration below is what it consults.

## use_case.json

One LLM use case, declared in a form the code reads at run time: classification and owner, the intended purpose, the explicit out-of-scope list, the model builds approved for this use, the required controls, and the acceptance thresholds. Its GOVERN and MAP content is the part that usually lives in a document nobody opens; here the wrapper hashes it into every audit record and enforces two of its clauses directly.

| Clause | How it is enforced |
|---|---|
| `govern.approved_models[].name` | A model not on the list is refused before any tokens are spent |
| `govern.approved_models[].digest` | The live weights are checked against the approved build; a mismatch is refused |
| `measure.acceptance_thresholds` | Output below threshold is flagged in the record and reported by `--verify` |
| `manage.review_required_before_use` | Output is logged as pending until a named reviewer records a decision |

Editing this file changes what the wrapper allows, which is the point: a digest change means new weights, and re-approving them is a deliberate human act standing in for committee sign-off. Keep it in version control and treat changes with the same seriousness as any other governance record.

The `measure.not_covered_by_this_use_case` list is deliberate. Naming what a control set does *not* cover is more useful than implying complete coverage, and it is the honest form of scope.

## prompt_log_template.jsonl

One JSON object per event, appended by the wrapper. Two record types: `call` for a model call, `sign_off` for a review decision against one.

| Field | Purpose |
|---|---|
| `run_id`, `timestamp_utc` | Which call, and when |
| `use_case` | Which declaration, which version, and its hash: the governance position the call was made under |
| `operator` | Who ran it. An audit record with no actor is weak evidence |
| `model.digest` | The content digest of the local weights, from Ollama's `/api/tags` |
| `model.digest_verification` | `verified`, or `waived` where the endpoint exposes no digest. Waivers are recorded, never silent |
| `parameters` | Decoding settings (temperature, seed) |
| `corpus` | Which source document was supplied, its hash, and how many citable sections |
| `prompt` | Template identifier and version, the full text, and its hash |
| `response` | The raw reply, its hash, and the parsed object |
| `validation` | Whether the reply matched the contract, which sections it cited, and which citations did not resolve |
| `latency_ms` | Performance record |
| `review` | `pending` until a `sign_off` record names a reviewer and a decision |
| `prev_chain_sha256`, `chain_sha256` | Each record hashes its predecessor's hash together with its own contents |

### Why the chain, and not just field hashes

A hash of a field, stored in the same record as that field, mostly proves the record is internally consistent. Anyone editing the text can recompute the hash, and deleting or reordering whole records leaves no trace at all. Chaining each record to the one before makes both detectable: altering a record breaks its own hash, and removing one breaks the link of every record after it. `--verify` recomputes the chain and reports the first line that does not follow.

This is tamper-*detection* within a file, not tamper-proofing. It does not survive an adversary willing to rewrite the whole log, which is what append-only storage, off-host replication, or periodic external timestamping are for. It does mean that a casually edited log stops verifying, which is the threat most teams actually face.

### Why structured output

Free text cannot be checked by code. The wrapper requires a JSON object with an answer, a list of cited section identifiers, and an explicit `not_covered` flag, then resolves every identifier against the supplied document. A citation to a section that does not exist is caught mechanically rather than by a reader who is short of time. This is the difference between asking "is this true?" and asking "does the citation support this?": the second question is faster and more reliable, and it surfaces confabulation directly.

## model_card_template.md

A one-page record per model (or fine-tuned adapter) in use: what it is, what it is for, what it was trained/evaluated on, known limitations, and who approved it. For fine-tuned models the card must pin all three of base model, dataset version, and adapter, because the adapter is meaningless without the other two.

## Where this lands against the frameworks

For US actuarial work these artefacts line up with ASOP 56's expectations around understanding, testing, and documenting models you use or rely on. Against the NIST AI RMF, `use_case.json` carries GOVERN and MAP content, the validation fields and thresholds are MEASURE, and the audit log, the sign-off gate and the digest pinning are MANAGE. For ISO/IEC 42001 they slot in as operational-control evidence.

Two gaps to be candid about, both of which need the task they measure rather than a wrapper: an evaluation suite against known-correct answers, which is what `examples/02_claim_classification.py` demonstrates in miniature, and prompt injection testing, which nothing here attempts.

---

For help, assistance, or more information: [globebyte.com](https://globebyte.com/)
