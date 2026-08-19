"""Fine-tune step 3: evaluate models side by side on the held-out test split.

Compares any two (or more) Ollama-served models on the same 40 test notes
the training never saw, reporting per-model accuracy, invalid-output rate
(format discipline), and the confusion pairs. Typical use: the prompted 8B
baseline against your fine-tuned 4B.

    python finetune/03_evaluate.py --models qwen3:8b claims-classifier

Note the asymmetry, which is the point of the comparison: the baseline gets
the full rulebook prompt from examples/02; the fine-tuned model gets only
the short instruction it was trained with, because the rules now live in
the adapter weights.
"""

import argparse
import json
import os
import re
from collections import Counter
from pathlib import Path

from openai import OpenAI

REPO = Path(__file__).resolve().parents[1]
LABELS = ["MOTOR_BI", "MOTOR_PD", "PROPERTY_WATER", "PROPERTY_FIRE",
          "LIABILITY_INJURY"]

BASELINE_SYSTEM = (
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
FINETUNED_SYSTEM = (
    "Classify the insurance claim note into exactly one category: MOTOR_BI, "
    "MOTOR_PD, PROPERTY_WATER, PROPERTY_FIRE, or LIABILITY_INJURY. Respond "
    "with the category code only.")


def strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def parse_label(raw: str) -> str | None:
    cleaned = strip_think(raw).upper()
    found = [lb for lb in LABELS if lb in cleaned]
    if len(found) == 1 and len(cleaned) < 40:
        return found[0]
    return None


def evaluate(client: OpenAI, model: str, system: str,
             cases: list[dict]) -> dict:
    correct, invalid = 0, 0
    confusion: Counter = Counter()
    for i, case in enumerate(cases, 1):
        note = case["messages"][1]["content"]
        gold = case["messages"][2]["content"]
        response = client.chat.completions.create(
            model=model, temperature=0, seed=42,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": note}],
        )
        predicted = parse_label(response.choices[0].message.content)
        if predicted is None:
            invalid += 1
        elif predicted == gold:
            correct += 1
        else:
            confusion[(gold, predicted)] += 1
        print(f"\r  {model}: {i}/{len(cases)}", end="", flush=True)
    print()
    return {"model": model, "n": len(cases), "correct": correct,
            "invalid": invalid, "confusion": confusion}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+",
                    default=["qwen3:8b", "claims-classifier"],
                    help="Ollama model names; a name containing "
                         "'claims-classifier' gets the short fine-tune prompt")
    args = ap.parse_args()

    test_path = REPO / "finetune" / "data" / "test.jsonl"
    cases = [json.loads(line) for line in
             test_path.read_text(encoding="utf-8").splitlines()]

    client = OpenAI(base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
                    api_key="ollama")

    reports = []
    for model in args.models:
        system = (FINETUNED_SYSTEM if "claims-classifier" in model
                  else BASELINE_SYSTEM)
        reports.append(evaluate(client, model, system, cases))

    print(f"\n{'model':<28}{'accuracy':>10}{'invalid':>10}")
    for r in reports:
        acc = f"{r['correct']}/{r['n']} ({r['correct'] / r['n']:.0%})"
        print(f"{r['model']:<28}{acc:>10}{r['invalid']:>10}")
    for r in reports:
        if r["confusion"]:
            print(f"\n{r['model']} confusions (gold -> predicted):")
            for (g, p), c in r["confusion"].most_common():
                print(f"  {g} -> {p}: {c}")


if __name__ == "__main__":
    main()
