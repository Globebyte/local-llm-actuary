# Model card: [model or adapter name]

| | |
|---|---|
| Model / adapter | e.g. claims-classifier v1 (QLoRA adapter, merged GGUF q4_k_m) |
| Base model | e.g. Qwen3-4B-Instruct-2507, Apache 2.0 |
| Serving runtime | e.g. Ollama x.y.z, local digest [...] |
| Owner | Name, role |
| Approved by / date | |

## Intended use

One paragraph: the task, the users, the decision the output feeds, and the human checkpoint between model output and any consequential action.

## Out of scope

Explicit non-uses. e.g. "Not for coverage decisions. Not for claims involving categories outside the five trained labels."

## Training data (fine-tuned models)

Dataset name and version; size and split; provenance (synthetic/real, source system); labelling rules reference; where the held-out test set lives.

## Evaluation

Test set, date, metrics (accuracy, invalid-output rate, confusions), versus which baseline. Link the evaluation script and the results file.

## Limitations and known failure modes

e.g. sensitivity to notes mixing injury and damage signals; behaviour on categories not in training; language/register drift from the synthetic training distribution.

## Monitoring and review

Sampling rate for human review, drift indicators watched, retraining triggers, review cadence.
