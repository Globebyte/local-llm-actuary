# Example 04: from a system that logs to a system that can refuse

Script: [`04_governance_wrapper.py`](04_governance_wrapper.py) · Practice area: any · Run: `python examples/04_governance_wrapper.py "How is the credibility factor set?"`

## The distinction this example is built on

Most "AI governance" in practice is documentation. A policy exists, a register has an entry, a model card was written at go-live, and none of it touches the running system. The system does what it does; the documents describe what it was supposed to do. When the two diverge (a model updated underneath you, an output used without review), nothing notices.

The distinction worth holding onto is between a log and a control. A log is written after the fact and asserts what happened. A control is consulted before the fact and can stop the call. This example does both, and its four controls are the reason it exists:

| | Control | The failure it prevents |
|---|---|---|
| GOVERN | Model must be on the approved list, and its digest must match | Running against weights nobody approved |
| MEASURE | Output must be JSON with citations that resolve against the corpus | A confident answer citing a section that does not exist |
| MANAGE | Each log record hashes its predecessor | A log edited or pruned after the fact |
| REVIEW | Output is `pending` until a named reviewer decides | Unreviewed output reaching a work product |

Each one can be made to fire, and the section below shows how.

## The declaration: governance the code reads

[`governance/use_case.json`](../governance/use_case.json) holds what usually lives in a document nobody opens: classification, owner, policy reference, intended purpose, the explicit out-of-scope list, the approved model builds, required controls, acceptance thresholds, decommission triggers.

The difference is that the wrapper reads it at run time. It hashes the file into every audit record, so a later reader can tell which version of the governance position a call was made under, and it enforces two clauses directly:

```json
"approved_models": [
  {
    "name": "qwen3:8b",
    "digest": "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41",
    "serving": "Ollama on localhost, weights never leave the machine"
  }
]
```

Point the script at a model that is not on that list and it refuses before spending a single token:

```
$ LLM_MODEL=qwen3:4b python examples/04_governance_wrapper.py "test"
Refused: model 'qwen3:4b' is not approved for use case AI-2026-014.
Approved: ['qwen3:8b']. Add it to use_case.json only with the approval that file represents.
```

Exit code 2, no call made. The declaration also carries a `not_covered_by_this_use_case` list, naming what these controls do *not* reach: retrieval quality, an evaluation suite, prompt injection testing. Naming the gaps is more useful than implying coverage, and it is the honest form of scope.

## Why the model digest, and why the obvious field is wrong

"Which model produced this output?" seems answered by recording `qwen3:8b`. It is not. A model tag is a moving pointer: the weights behind `qwen3:8b` today and in six months may differ, and an output you need to explain to a reviewer next year was produced by a specific build.

The wrapper records the content digest of the local weights, read from Ollama's `/api/tags`:

```
500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41
```

That is the manifest digest, the same value `ollama list` shows abbreviated as the model ID. It is content-addressed, so it identifies the build rather than the installation.

An earlier version of this example used `/api/show` and combined `quantization_level` with `modified_at`. Both parts of that were wrong in an instructive way. `/api/show` carries no digest field at all. And `modified_at` records when *you pulled the model onto this machine*, so two actuaries holding byte-identical weights record different values, and re-pulling changes yours. It looked like provenance and was machine-local noise. If you take one implementation detail from this example, take this one: check that the field you are recording as provenance actually identifies what you think it identifies.

The digest is what makes provider change management possible rather than aspirational. Change the approved digest and the control fires:

```
Refused: model digest does not match the approved build.
  approved: deadbeefdeadbeef...
  observed: 500a1f067a9f7826...
This is the control working, not a failure. The weights behind 'qwen3:8b' have changed.
Re-run the evaluation suite, then record the new digest in use_case.json if the change is approved.
```

Editing the declaration to accept a new digest is a deliberate human act, standing in for committee re-approval. That is the intended friction.

Endpoints that expose no digest (LM Studio, for instance) are handled by `--allow-unverified-digest`, which proceeds and writes `"digest_verification": "waived"` into the record. A waiver that is recorded is governance; a waiver that is silent is a gap.

## Structured output, and why free text cannot be checked

The prompt requires a single JSON object:

```json
{"answer": "...", "citations": ["S4"], "not_covered": false}
```

Then [`validate()`](04_governance_wrapper.py#L235-L281) checks it in code, asking two separate questions:

1. Does it have the promised shape? Valid JSON, an object, the three keys present with the right types, and one small but real rule: an answer must cite something. "Answered but cited nothing" is a validation error, not an acceptable response.
2. Do the citations resolve? Every `S<n>` is checked against the sections actually supplied. Anything unresolvable is reported, never quietly dropped.

The second check is the one that catches confabulation mechanically. [Example 03](03_methodology_qa.md) asks the model to cite; this one *verifies* the citation points at something real, and does it in code rather than relying on a reader who is short of time.

One practical wrinkle worth knowing: asked for `"S4"`, the model sometimes returns `"S4: Mortality assumptions"`. A regular expression extracts the identifier rather than failing the whole response, because rejecting a substantively correct answer over a cosmetic formatting variance trains people to switch the validator off. Tolerate shape variance; never tolerate an unresolvable citation.

Free text cannot be checked this way at all, which is the entire argument for the JSON contract. Prose containing "as set out in section 3" gives code nothing to verify.

## The hash chain, and what it does not defend against

The previous version of this example recorded `prompt_sha256` and `response_sha256` and the repository described them as tamper-evident. They were not, and the reasoning is worth following because the mistake is extremely common.

A hash of a field, stored in the same record as that field, proves the record is internally consistent. Anyone editing the text can recompute the hash. And deleting or reordering entire records leaves no trace whatsoever, because nothing ties one record to the next.

Chaining fixes both. Each record carries the previous record's chain value, and its own is computed over both:

```
chain_sha256 = SHA256( prev_chain_sha256 + canonical_json(record without chain_sha256) )
```

`canonical_json` sorts keys and uses fixed separators so the hash is reproducible rather than dependent on serialisation accident. Now editing a record breaks its own hash, and removing one breaks the link of every record after it. `--verify` recomputes the whole chain and reports the first line that does not follow:

```
$ python examples/04_governance_wrapper.py --verify
Audit log: results/prompt_log.jsonl
  records:         5 (2 calls, 1 sign-offs)
  chain:           BROKEN
    line 3: contents do not match its own chain hash
  awaiting review: 1
```

Be precise about the strength of this claim. It is tamper detection within a file, not tamper-proofing. It does nothing against an adversary willing to rewrite the entire log and recompute every hash forward, because they hold everything needed to do so. Defending against that requires something outside the file: append-only storage, replication to a host the operator cannot write to, or periodically publishing the current chain head somewhere immutable. What chaining does buy, and it is worth having, is that a casually edited log stops verifying, which is the threat most teams actually face.

Records written before the chain existed are reported as `unchained ... not verifiable` rather than as tampering, because an honest audit tool distinguishes "cannot be checked" from "failed the check".

## The sign-off gate

Every call is logged with `"review": {"status": "pending", ...}` and is not usable until a named reviewer records a decision:

```bash
python examples/04_governance_wrapper.py --sign-off <run_id> --accept \
    --reviewer "A. Actuary" --note "Checked S4 against the document."
```

Three design decisions here.

Sign-off is a separate command, not a prompt at the end of the call. In real work review happens later than generation and usually by someone else. A control that requires the reviewer to be sitting at the keyboard when the model runs is modelling something that does not happen.

The decision is appended, not patched in. The `pending` record stays in the log. That is what lets a reader see that review occurred at all, and when, and by whom: a record silently mutated from pending to accepted preserves no evidence of the gap between them.

A reviewer name is mandatory. `--reviewer` with an empty value is refused, because a sign-off without a name is not a sign-off. Duplicate sign-offs are refused too: the first decision stands, and revisiting it is an incident to record rather than a field to overwrite.

`--verify` lists everything still awaiting review, and separately flags any run that failed validation with `below threshold: (must not be accepted)`.

## The record

One JSON object per event, two record types. Beyond the obvious fields, four are there for reasons worth naming:

- `use_case`: id, declaration version, and declaration hash. Which governance position applied.
- `operator`: user and host. An audit record with no actor is weak evidence.
- `corpus`: path, content hash, section count. Which document version was actually supplied.
- `prompt.template_id` / `template_version`: which prompt, as a versioned artefact. Prompts change; outputs must remain attributable to the one that produced them.

Full field table in [`governance/README.md`](../governance/README.md).

## Where this lands against the frameworks

| NIST AI RMF | Artefact here |
|---|---|
| GOVERN | `use_case.json`: classification, owner, policy reference, approved models, decommission triggers |
| MAP | `use_case.json`: intended purpose, out-of-scope list, `stakeholders`, confabulation impact analysis |
| MEASURE | Validation fields, acceptance thresholds, citation resolution rate |
| MANAGE | Hash-chained audit log, sign-off gate, digest pinning as change control |

For US actuarial work the ASOP 56 reading is direct: understand the model, test it, document limitations, and be explicit about reliance on a model developed by others. The digest is the "which model" answer, the declaration is the intended-use and limitations answer, and the log is the evidence.

## Deliberately out of scope

Three gaps, stated because a control set that claims completeness invites less scrutiny than it deserves:

No evaluation suite. Acceptance thresholds are declared and checked per call, but nothing here runs a set of known-correct questions and tracks pass rates over time. That belongs with the task it measures ([example 02](02_claim_classification.md) is the miniature version), and it is the single most valuable artefact most actuarial teams have never built.

No prompt injection testing. The corpus here is a document you control. A corpus containing anything a third party can write (emails, claim notes, submitted documents) introduces the risk that retrieved text carries instructions the model follows. Nothing in this example tests for it.

No retrieval. Every section is supplied rather than retrieved, so retrieval quality is not a variable. That keeps the example about governing the call. A real system combines this wrapper with example 03's retrieval, and then corpus version and retrieval quality both become governed concerns.

## One maintenance obligation

The declaration pins `qwen3:8b` to the digest current at the time of writing. Identical for anyone pulling the same tag, but when the tag is republished, this example will refuse to run until the digest is updated.

That is the control behaving exactly as designed, and the refusal message says so. It is also a standing obligation on this repository, and worth understanding before you copy the pattern: version pinning transfers work from the failure you cannot see to the maintenance you can. That is a good trade, and it is still a trade.

## Things to try

- Run `--dry-run` first. It prints the declaration summary, the citable sections, and the system prompt without touching the server, which is the fastest way to see what is being enforced.
- Make each control fire: set `LLM_MODEL` to something unapproved; edit the digest in the declaration; open `results/prompt_log.jsonl`, change one character inside a record, and run `--verify`; delete a whole line and verify again. Watching the difference between "contents do not match its own chain hash" and "does not follow the previous record" makes the mechanism concrete.
- Ask something the document does not cover and read the record. `not_covered` is `true`, `citations` is empty, and validation passes: a refusal is a valid output, not a failure.
- Sign a run off, then try again. The refusal on the second attempt is the control that stops a rejected output being quietly re-approved.

---

For help, assistance, or more information: [globebyte.com](https://globebyte.com/)
