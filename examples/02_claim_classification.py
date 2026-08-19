"""02: Classify free-text claim notes into reserving categories (GI/P&C).

The pattern that makes a local model usable for real work:

    1. A strict output contract: exactly one label from a fixed list.
    2. Validation in code: the model proposes, your code disposes.
    3. Measurement: accuracy against a labelled sample, not vibes.
    4. A results file you can audit.

Run:
    python examples/02_claim_classification.py              # 25-note sample
    python examples/02_claim_classification.py --all        # all 200 notes
    python examples/02_claim_classification.py --dry-run    # show prompts only
"""

import argparse
import csv
import os
import re
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LABELS = ["MOTOR_BI", "MOTOR_PD", "PROPERTY_WATER", "PROPERTY_FIRE",
          "LIABILITY_INJURY"]

# The prompt is versioned in prompts/claim_classifier_v1.md with rationale.
SYSTEM = (
    "You classify insurance claim notes into exactly one reserving category.\n"
    "Categories and rules:\n"
    "- MOTOR_BI: motor incident where any person is injured or reports "
    "symptoms, however minor, whenever reported. Injury outranks damage.\n"
    "- MOTOR_PD: motor incident, vehicle or property damage only, no injury "
    "indicated.\n"
    "- PROPERTY_WATER: escape of water or internal leak damage at the insured "
    "property.\n"
    "- PROPERTY_FIRE: fire, smoke, or fire-suppression damage; origin "
    "governs, so water used to extinguish a fire is a fire loss.\n"
    "- LIABILITY_INJURY: third-party injury on or arising from the insured "
    "premises or operations.\n"
    "Respond with the category code only. No punctuation, no explanation. "
    "/no_think"
)


def strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def parse_label(raw: str) -> str | None:
    """Accept the label only if it is unambiguous. Anything else is invalid.

    An invalid response is information: it is a formatting failure you count,
    log, and (in production) route to a human, never silently repair.
    """
    cleaned = strip_think(raw).upper()
    found = [lb for lb in LABELS if lb in cleaned]
    if len(found) == 1 and len(cleaned) < 40:
        return found[0]
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="classify all rows")
    ap.add_argument("--n", type=int, default=25, help="sample size (default 25)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the first three prompts and exit (no model call)")
    args = ap.parse_args()

    with open(REPO / "data" / "synthetic_claims.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not args.all:
        rows = rows[: args.n]

    if args.dry_run:
        for row in rows[:3]:
            print("SYSTEM:", SYSTEM, "\nUSER:", row["note"], "\n---")
        return

    from openai import OpenAI  # imported here so --dry-run needs no server
    client = OpenAI(base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
                    api_key="ollama")
    model = os.getenv("LLM_MODEL", "qwen3:8b")

    results, correct, invalid = [], 0, 0
    confusion: Counter = Counter()
    for i, row in enumerate(rows, 1):
        response = client.chat.completions.create(
            model=model, temperature=0, seed=42,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": row["note"]}],
        )
        predicted = parse_label(response.choices[0].message.content)
        gold = row["category"]
        if predicted is None:
            invalid += 1
        elif predicted == gold:
            correct += 1
        else:
            confusion[(gold, predicted)] += 1
        results.append({**row, "predicted": predicted or "INVALID"})
        print(f"\r{i}/{len(rows)}", end="", flush=True)

    out_dir = REPO / "results"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "claim_classification_results.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["claim_id", "note", "category", "predicted"])
        w.writeheader()
        w.writerows(results)

    n = len(rows)
    print(f"\n\nModel: {model}")
    print(f"Accuracy: {correct}/{n} ({correct / n:.1%})")
    print(f"Invalid outputs (format failures): {invalid}/{n}")
    if confusion:
        print("Top confusions (gold -> predicted):")
        for (g, p), c in confusion.most_common(5):
            print(f"  {g} -> {p}: {c}")
    print(f"Row-level results: {out_path}")


if __name__ == "__main__":
    sys.exit(main())
