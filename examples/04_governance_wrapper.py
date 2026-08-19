"""04: A governance wrapper for local model calls.

Running the model locally solves the channel problem. It does not solve the
governance problem. This wrapper is the smallest thing that behaves like a
governed system rather than a logged one, and the difference is that it can
refuse. Four controls, each doing work at run time:

    GOVERN   The use case is declared in governance/use_case.json: intended
             purpose, out-of-scope uses, and the model builds approved for it.
             The wrapper reads that file, hashes it into every record, and
             will not call a model whose digest is not on the approved list.

    MEASURE  The model must answer as JSON citing section identifiers, and
             every identifier is resolved against the corpus in code. A
             citation to a section that does not exist is caught here, not
             by the reader. Free text cannot be checked this way; that is the
             argument for structured output.

    MANAGE   Each record carries the hash of the record before it, so the log
             detects deletion and reordering, not merely editing in place. A
             per-record hash sitting inside the record it hashes proves very
             little on its own.

    REVIEW   Output is logged as pending and is not usable until a named
             reviewer records a decision against the run identifier. Sign-off
             is a separate act, because in real work review happens later
             than generation and by someone else.

Deterministic-leaning settings (temperature 0, fixed seed) reduce run-to-run
variation but do not guarantee identical output across hardware, runtimes, or
model builds. The log, not the settings, is what makes a run auditable.

What this example does not do: retrieval quality (example 03), evaluation
against ground truth (example 02), or prompt injection testing. The
declaration says so explicitly, which is the honest form of scope.

Run:
    python examples/04_governance_wrapper.py "How is the credibility factor set?"
    python examples/04_governance_wrapper.py --sign-off <run_id> --accept --reviewer "A. Actuary"
    python examples/04_governance_wrapper.py --verify
    python examples/04_governance_wrapper.py --dry-run     # no server needed
"""

import argparse
import datetime as dt
import getpass
import hashlib
import json
import os
import re
import socket
import sys
import time
import urllib.request
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DECLARATION_PATH = REPO / "governance" / "use_case.json"
CORPUS_PATH = REPO / "data" / "sample_methodology.md"
LOG_PATH = REPO / "results" / "prompt_log.jsonl"

BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
MODEL = os.getenv("LLM_MODEL", "qwen3:8b")

SCHEMA_VERSION = "2"
PROMPT_TEMPLATE_ID = "methodology-qa"
PROMPT_TEMPLATE_VERSION = "1.0.0"

SYSTEM_PROMPT = (
    "You answer questions about an internal valuation methodology document, "
    "using ONLY the numbered sections supplied. Reply with a single JSON "
    "object and nothing else, with exactly these keys: "
    '"answer" (string), "citations" (array of section identifiers such as '
    '"S3" that support the answer), and "not_covered" (boolean, true if the '
    "sections do not address the question). If not_covered is true, leave "
    "citations empty and do not answer from general knowledge. /no_think"
)


class GovernanceError(Exception):
    """A control refused the call. Not a bug; the wrapper working."""


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical(obj: dict) -> str:
    """Stable serialisation, so a hash of a record is reproducible."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def native_url(path: str) -> str:
    """Ollama's own API sits alongside the OpenAI-compatible /v1 prefix."""
    return BASE_URL.rsplit("/v1", 1)[0] + path


def ollama_get(path: str, timeout: int = 5) -> dict:
    with urllib.request.urlopen(native_url(path), timeout=timeout) as r:
        return json.load(r)


def model_digest(model: str) -> str:
    """The content digest of the local weights, from /api/tags.

    This is the manifest digest, the same value 'ollama list' shows as ID.
    It identifies the build: 'qwen3:8b' today and 'qwen3:8b' in six months
    may be different weights, and this is the field that tells them apart.

    Note that /api/show does not carry a digest, and its modified_at is only
    when the model was pulled onto this machine, which differs between two
    analysts holding byte-identical weights. It is not a substitute.
    """
    for m in ollama_get("/api/tags").get("models", []):
        if (m.get("name") or m.get("model")) == model:
            return m.get("digest") or ""
    raise GovernanceError(
        f"model {model!r} is not present on the local server. "
        f"Pull it first: ollama pull {model}")


def runtime_version() -> str:
    try:
        return "ollama " + ollama_get("/api/version").get("version", "?")
    except Exception:
        return "unknown"


def load_declaration() -> tuple[dict, str]:
    """Read the use case declaration and hash it exactly as stored.

    The hash goes into every record so that a later reader can tell which
    version of the governance position the call was made under.
    """
    raw = DECLARATION_PATH.read_text(encoding="utf-8")
    return json.loads(raw), sha256(raw)


def sections(markdown: str) -> list[dict]:
    """Split the document into citable units, one per heading.

    Same convention as example 03, so a citation means the same thing in
    both. Here every section is supplied rather than retrieved: this example
    is about governing the call, not about retrieval.
    """
    out, current = [], {"heading": "Preamble", "text": ""}
    for line in markdown.splitlines():
        if line.startswith("#"):
            if current["text"].strip():
                out.append(current)
            current = {"heading": line.lstrip("# ").strip(), "text": ""}
        else:
            current["text"] += line + "\n"
    if current["text"].strip():
        out.append(current)
    kept = [s for s in out if len(s["text"].strip()) > 40]
    for i, s in enumerate(kept, 1):
        s["id"] = f"S{i}"
    return kept


def preflight(decl: dict, model: str, allow_unverified: bool) -> dict:
    """Check the call against the declaration before any tokens are spent.

    Returns the model record for the log. Raises GovernanceError if the
    model is not approved for this use case, which is the control that makes
    provider change management possible rather than aspirational.
    """
    approved = {m["name"]: m for m in decl["govern"]["approved_models"]}
    if model not in approved:
        raise GovernanceError(
            f"model {model!r} is not approved for use case "
            f"{decl['use_case_id']}. Approved: {sorted(approved)}. "
            f"Add it to {DECLARATION_PATH.name} only with the approval that "
            f"file represents.")

    expected = approved[model]["digest"]
    try:
        observed = model_digest(model)
        verification = "verified"
    except GovernanceError:
        raise
    except Exception as exc:
        if not allow_unverified:
            raise GovernanceError(
                f"could not read the model digest ({exc}). A non-Ollama "
                f"endpoint may not expose one. Re-run with "
                f"--allow-unverified-digest to proceed and have the waiver "
                f"recorded in the log.")
        observed, verification = "", "waived"

    if verification == "verified" and observed != expected:
        raise GovernanceError(
            f"model digest does not match the approved build.\n"
            f"  approved: {expected}\n"
            f"  observed: {observed}\n"
            f"This is the control working, not a failure. The weights behind "
            f"{model!r} have changed. Re-run the evaluation suite, then "
            f"record the new digest in {DECLARATION_PATH.name} if the change "
            f"is approved.")

    return {"name": model, "digest": observed or None,
            "digest_expected": expected, "digest_verification": verification,
            "runtime": runtime_version(), "approved": True}


def chain_tail() -> str:
    """The hash of the last record, or a fixed genesis value for a new log."""
    if not LOG_PATH.exists():
        return "genesis"
    last = "genesis"
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        if line.strip():
            last = json.loads(line).get("chain_sha256", last)
    return last


def append_record(record: dict) -> dict:
    """Link the record to its predecessor and append it.

    chain_sha256 covers the previous chain value and this record's content,
    so removing or reordering any line breaks every hash after it.
    """
    record["prev_chain_sha256"] = chain_tail()
    record["chain_sha256"] = sha256(record["prev_chain_sha256"]
                                    + canonical(record))
    LOG_PATH.parent.mkdir(exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def validate(raw: str, valid_ids: set) -> dict:
    """Check the model's reply against the contract, in code.

    Two distinct questions: does the output have the promised shape, and do
    its citations point at sections that exist? The second is the one that
    catches confabulation.
    """
    result = {"schema_valid": False, "errors": [], "citations": [],
              "unresolved": [], "citation_resolution_rate": None,
              "parsed": None}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        result["errors"].append(f"not valid JSON: {exc}")
        return result
    if not isinstance(parsed, dict):
        result["errors"].append("top level is not a JSON object")
        return result

    for key, kind in (("answer", str), ("citations", list),
                      ("not_covered", bool)):
        if key not in parsed:
            result["errors"].append(f"missing key {key!r}")
        elif not isinstance(parsed[key], kind):
            result["errors"].append(f"{key!r} is not {kind.__name__}")
    if result["errors"]:
        result["parsed"] = parsed
        return result

    # The model may return "S3" or "S3: Mortality assumptions". Take the
    # identifier and resolve it; anything unresolvable is reported, never
    # quietly dropped.
    cited = []
    for item in parsed["citations"]:
        match = re.search(r"S\d+", str(item))
        cited.append(match.group(0) if match else str(item))

    unresolved = [c for c in cited if c not in valid_ids]
    if not parsed["not_covered"] and not cited:
        result["errors"].append("answered but cited nothing")

    result.update(schema_valid=not result["errors"], parsed=parsed,
                  citations=cited, unresolved=unresolved,
                  citation_resolution_rate=(
                      round(1 - len(unresolved) / len(cited), 4)
                      if cited else None))
    return result


def governed_call(question: str, allow_unverified: bool) -> dict:
    decl, decl_sha = load_declaration()
    model_record = preflight(decl, MODEL, allow_unverified)

    corpus_text = CORPUS_PATH.read_text(encoding="utf-8")
    chunks = sections(corpus_text)
    valid_ids = {c["id"] for c in chunks}
    context = "\n\n".join(f"[{c['id']}] {c['heading']}\n{c['text'].strip()}"
                          for c in chunks)
    user_prompt = f"Sections:\n{context}\n\nQuestion: {question}"

    from openai import OpenAI
    client = OpenAI(base_url=BASE_URL, api_key="ollama")

    start = time.perf_counter()
    response = client.chat.completions.create(
        model=MODEL, temperature=0, seed=42,
        response_format={"type": "json_object"},
        messages=[{"role": "system", "content": SYSTEM_PROMPT},
                  {"role": "user", "content": user_prompt}],
    )
    latency_ms = round((time.perf_counter() - start) * 1000)
    raw = response.choices[0].message.content or ""
    checks = validate(raw, valid_ids)

    thresholds = decl["measure"]["acceptance_thresholds"]
    rate = checks["citation_resolution_rate"]
    meets = (checks["schema_valid"]
             and (rate is None or rate >= thresholds["citation_resolution_rate"]))

    record = append_record({
        "record_type": "call",
        "schema_version": SCHEMA_VERSION,
        "run_id": str(uuid.uuid4()),
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "use_case": {"id": decl["use_case_id"],
                     "declaration_version": decl["declaration_version"],
                     "declaration_sha256": decl_sha},
        "operator": {"user": getpass.getuser(), "host": socket.gethostname()},
        "model": model_record,
        "parameters": {"temperature": 0, "seed": 42},
        "corpus": {"path": str(CORPUS_PATH.relative_to(REPO)).replace("\\", "/"),
                   "sha256": sha256(corpus_text), "sections": len(chunks)},
        "prompt": {"template_id": PROMPT_TEMPLATE_ID,
                   "template_version": PROMPT_TEMPLATE_VERSION,
                   "system": SYSTEM_PROMPT, "user": user_prompt,
                   "sha256": sha256(SYSTEM_PROMPT + "\n" + user_prompt)},
        "response": {"raw": raw, "raw_sha256": sha256(raw),
                     "parsed": checks["parsed"]},
        "validation": {k: checks[k] for k in
                       ("schema_valid", "errors", "citations", "unresolved",
                        "citation_resolution_rate")} | {"meets_thresholds": meets},
        "latency_ms": latency_ms,
        "review": {"status": "pending", "reviewer": None,
                   "decided_at": None, "note": None},
    })
    return {"record": record, "checks": checks, "chunks": chunks,
            "meets": meets}


def sign_off(run_id: str, decision: str, reviewer: str, note: str) -> dict:
    """Record a named reviewer's decision against an earlier call.

    A separate act, appended rather than patched: the pending state stays in
    the log, which is what lets a reader see that review happened at all.
    """
    if not LOG_PATH.exists():
        raise GovernanceError(f"no audit log at {LOG_PATH}")
    calls = [json.loads(l) for l in
             LOG_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
    target = next((r for r in calls if r.get("run_id") == run_id
                   and r.get("record_type") == "call"), None)
    if target is None:
        raise GovernanceError(f"no call record with run_id {run_id!r}")
    if any(r.get("record_type") == "sign_off" and r.get("run_id") == run_id
           for r in calls):
        raise GovernanceError(f"run {run_id} has already been signed off")

    return append_record({
        "record_type": "sign_off",
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "reviewer": reviewer,
        "decision": decision,
        "note": note,
        "signs_chain_sha256": target["chain_sha256"],
    })


def verify_log() -> int:
    """Recompute the chain and report anything the log cannot account for."""
    if not LOG_PATH.exists():
        print(f"No audit log at {LOG_PATH}")
        return 0
    lines = [l for l in LOG_PATH.read_text(encoding="utf-8").splitlines()
             if l.strip()]
    prev, broken, legacy, calls, decisions = "genesis", [], [], [], {}

    for n, line in enumerate(lines, 1):
        rec = json.loads(line)
        # Records written before the chain existed carry no link and cannot be
        # verified. Say so rather than reporting them as tampering.
        if "chain_sha256" not in rec:
            legacy.append(n)
        else:
            body = {k: v for k, v in rec.items() if k != "chain_sha256"}
            if rec.get("prev_chain_sha256") != prev:
                broken.append((n, "does not follow the previous record"))
            elif sha256(prev + canonical(body)) != rec["chain_sha256"]:
                broken.append((n, "contents do not match its own chain hash"))
            prev = rec["chain_sha256"]
        if rec.get("record_type") == "call":
            calls.append(rec)
        elif rec.get("record_type") == "sign_off":
            decisions[rec["run_id"]] = rec

    print(f"Audit log: {LOG_PATH}")
    print(f"  records:         {len(lines)} ({len(calls)} calls, "
          f"{len(decisions)} sign-offs)")
    print(f"  chain:           {'intact' if not broken else 'BROKEN'}")
    for n, why in broken:
        print(f"    line {n}: {why}")
    if legacy:
        print(f"  unchained:       {len(legacy)} record(s) predate schema "
              f"v{SCHEMA_VERSION}; not verifiable")

    chained_calls = [r for r in calls if "chain_sha256" in r]
    pending = [r for r in chained_calls if r["run_id"] not in decisions]
    failed = [r for r in chained_calls
              if not r.get("validation", {}).get("meets_thresholds", True)]
    print(f"  awaiting review: {len(pending)}")
    for r in pending:
        print(f"    {r['run_id']}  {r['timestamp_utc']}")
    if failed:
        print(f"  below threshold: {len(failed)} (must not be accepted)")
        for r in failed:
            reasons = r["validation"]["errors"] or r["validation"]["unresolved"]
            print(f"    {r['run_id']}  {reasons}")
    return 1 if broken else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("question", nargs="?",
                    default="How is the credibility factor for mortality set?")
    ap.add_argument("--dry-run", action="store_true",
                    help="show the declaration and prompt; no model call")
    ap.add_argument("--verify", action="store_true",
                    help="check the audit log chain and list pending reviews")
    ap.add_argument("--sign-off", metavar="RUN_ID",
                    help="record a review decision against a run")
    ap.add_argument("--accept", action="store_true")
    ap.add_argument("--reject", action="store_true")
    ap.add_argument("--reviewer", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--allow-unverified-digest", action="store_true",
                    help="proceed without a digest, recording the waiver")
    args = ap.parse_args()

    try:
        if args.verify:
            return verify_log()

        if args.sign_off:
            if args.accept == args.reject:
                raise GovernanceError("choose exactly one of --accept, --reject")
            if not args.reviewer.strip():
                raise GovernanceError(
                    "--reviewer is required: a sign-off without a name is not "
                    "a sign-off")
            rec = sign_off(args.sign_off,
                           "accepted" if args.accept else "rejected",
                           args.reviewer.strip(), args.note)
            print(f"{rec['decision']} by {rec['reviewer']} "
                  f"for run {rec['run_id']}")
            print(f"Recorded in {LOG_PATH}")
            return 0

        decl, decl_sha = load_declaration()
        if args.dry_run:
            chunks = sections(CORPUS_PATH.read_text(encoding="utf-8"))
            print(f"Use case {decl['use_case_id']} v"
                  f"{decl['declaration_version']} ({decl_sha[:12]}...)")
            print(f"  purpose:  {decl['map']['intended_purpose'][:100]}...")
            print(f"  approved: "
                  f"{[m['name'] for m in decl['govern']['approved_models']]}")
            print(f"  controls: {', '.join(decl['measure']['required_controls'])}")
            print(f"\n{len(chunks)} citable sections:")
            for c in chunks:
                print(f"  [{c['id']}] {c['heading']}")
            print(f"\nSystem prompt:\n{SYSTEM_PROMPT}")
            return 0

        out = governed_call(args.question, args.allow_unverified_digest)
        rec, checks = out["record"], out["checks"]
        parsed = checks["parsed"] or {}

        print(f"Q: {args.question}\n")
        if checks["schema_valid"] and parsed.get("not_covered"):
            print("The document does not cover this question.")
        elif checks["schema_valid"]:
            print(parsed["answer"])
            headings = {c["id"]: c["heading"] for c in out["chunks"]}
            print("\nCited:")
            for c in checks["citations"]:
                print(f"  [{c}] {headings.get(c, 'UNRESOLVED')}")
        else:
            print("Output rejected by validation:")
            for e in checks["errors"]:
                print(f"  - {e}")

        if checks["unresolved"]:
            print(f"\nUnresolved citations: {checks['unresolved']}")

        print(f"\nrun_id:  {rec['run_id']}")
        print(f"model:   {MODEL} @ {(rec['model']['digest'] or 'unverified')[:12]}")
        print(f"status:  pending review"
              f"{'' if out['meets'] else ' (BELOW THRESHOLD, do not accept)'}")
        print(f"log:     {LOG_PATH}")
        print(f"\nSign off with:\n  python {Path(__file__).name} "
              f"--sign-off {rec['run_id']} --accept --reviewer \"Your Name\"")
        return 0

    except GovernanceError as exc:
        print(f"Refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
