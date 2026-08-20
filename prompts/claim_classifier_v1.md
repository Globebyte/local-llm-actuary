# Claim classifier prompt, v1

Used by: `examples/02_claim_classification.py`, and as the baseline system prompt in `finetune/03_evaluate.py`.

## Prompt

```
You classify insurance claim notes into exactly one reserving category.
Categories and rules:
- MOTOR_BI: motor incident where any person is injured or reports symptoms, however minor, whenever reported. Injury outranks damage.
- MOTOR_PD: motor incident, vehicle or property damage only, no injury indicated.
- PROPERTY_WATER: escape of water or internal leak damage at the insured property.
- PROPERTY_FIRE: fire, smoke, or fire-suppression damage; origin governs, so water used to extinguish a fire is a fire loss.
- LIABILITY_INJURY: third-party injury on or arising from the insured premises or operations.
Respond with the category code only. No punctuation, no explanation. /no_think
```

## Rationale

- Rules, not just labels. The two tie-break rules (injury outranks damage; origin governs) exist because the dataset's hard cases exist. Label definitions belong in the prompt, in the data README, and in the evaluation, and they must be the same in all three.
- Output contract. "Category code only" makes the response machine-parseable; the parser in code still validates rather than trusting.
- `/no_think`. Disables Qwen3's reasoning block for deterministic, low-latency classification. Harmless on models that ignore it.

## Change log

- v1: initial version, paired with `data/synthetic_claims.csv` labelling rules.

---

For help, assistance, or more information: [globebyte.com](https://globebyte.com/)
