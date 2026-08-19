"""Fine-tune step 1: turn the labelled claims into chat-format training data.

Produces:
    finetune/data/train.jsonl   160 examples (Unsloth / Hugging Face)
    finetune/data/test.jsonl     40 held-out examples, never trained on
    finetune/data/mlx/{train,valid,test}.jsonl   same data, MLX-LM layout

Each record is a three-turn chat: a short system instruction, the claim note,
and the gold label as the assistant reply. The system prompt is deliberately
shorter than the prompted baseline in examples/02: teaching the rules to the
weights is the point of the exercise, so the fine-tuned model should not need
the rulebook restated at inference time.

The test split is sacred. It is the same 40 notes for every model you
evaluate, it is never used in training, and every accuracy claim you make
comes from it. Run this before training:

    python finetune/01_prepare_dataset.py
"""

import csv
import json
import random
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "finetune" / "data"
SEED = 20260721
TEST_PER_CLASS = 8  # 8 x 5 classes = 40 test rows

SYSTEM = ("Classify the insurance claim note into exactly one category: "
          "MOTOR_BI, MOTOR_PD, PROPERTY_WATER, PROPERTY_FIRE, or "
          "LIABILITY_INJURY. Respond with the category code only.")


def to_record(note: str, label: str) -> dict:
    return {"messages": [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": note},
        {"role": "assistant", "content": label},
    ]}


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> None:
    with open(REPO / "data" / "synthetic_claims.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    rng = random.Random(SEED)
    by_class: dict[str, list[dict]] = {}
    for row in rows:
        by_class.setdefault(row["category"], []).append(row)

    train, test = [], []
    for label, items in sorted(by_class.items()):
        rng.shuffle(items)
        test.extend(items[:TEST_PER_CLASS])       # stratified held-out split
        train.extend(items[TEST_PER_CLASS:])
    rng.shuffle(train)
    rng.shuffle(test)

    write_jsonl(OUT / "train.jsonl",
                [to_record(r["note"], r["category"]) for r in train])
    write_jsonl(OUT / "test.jsonl",
                [to_record(r["note"], r["category"]) for r in test])

    # MLX-LM (Apple Silicon) expects train/valid/test files in one folder.
    valid = train[-16:]
    write_jsonl(OUT / "mlx" / "train.jsonl",
                [to_record(r["note"], r["category"]) for r in train[:-16]])
    write_jsonl(OUT / "mlx" / "valid.jsonl",
                [to_record(r["note"], r["category"]) for r in valid])
    write_jsonl(OUT / "mlx" / "test.jsonl",
                [to_record(r["note"], r["category"]) for r in test])

    print(f"train: {len(train)}  test: {len(test)} (stratified, seed {SEED})")
    print(f"Written under {OUT}")


if __name__ == "__main__":
    main()
