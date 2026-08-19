# Fine-tuning: teaching the rules to the weights

Scripts: [`01_prepare_dataset.py`](01_prepare_dataset.py) · [`02_finetune_qlora.py`](02_finetune_qlora.py) · [`03_evaluate.py`](03_evaluate.py) · Practice area: GI / P&C · Read first: [example 02](../examples/02_claim_classification.md)

## What this example is for

[Example 02](../examples/02_claim_classification.md) took an 8B model, handed it a carefully written rulebook in the system prompt, and measured how well it sorted claim notes into five reserving categories. This example asks a different question: can a smaller model that has been taught the rules beat a larger model that has to be told them every time?

The answer here is that it draws, 95 per cent against 95 per cent, and the draw is the interesting result, because the two models are not paying the same price for it. The fine-tuned model is half the size, needs a quarter of the prompt, and holds its output format without being asked. That is the economic case for fine-tuning in a sentence, and the rest of this document is about how to get there and how to know whether you did.

## First: do not fine-tune yet

Prompting is faster, reversible, model-agnostic, and requires no GPU. Exhaust it. The honest triggers for training are narrow:

| Wall you have hit | What fine-tuning buys |
|---|---|
| Format discipline | You need exactly one label, every time, parseable by code, and the prompted model still editorialises on a few per cent of calls |
| Domain vocabulary | Your notes are dense with house shorthand (FNOL, EL/PL, NSD, *insd*) that a general model half-understands and cannot be taught reliably in a prompt |
| Economics | A small fine-tuned model matches a much larger prompted one, which changes what runs on a standard corporate laptop |

Note what is *not* on that list. Fine-tuning does not add knowledge you failed to supply: for that you want retrieval, which is [example 03](../examples/03_methodology_qa.md). It does not fix an ambiguous rulebook; it bakes the ambiguity in permanently and makes it harder to see. And it does not improve open-ended reasoning. If your labels are inconsistent, training on them converts a prompt problem into a weights problem, which is strictly worse, because a prompt can be edited in a text file and reviewed in a pull request while an adapter has to be retrained and re-evaluated.

## What QLoRA actually is

Not retraining. Three ideas stacked, and each one is what makes the next affordable:

Quantisation. The 4B base model is loaded with its weights compressed to 4 bits each instead of 16. That is roughly a quarter of the memory, at some cost in numerical precision. The base is then frozen, never updated.

Low-rank adaptation. Instead of changing a large weight matrix `W` directly, you learn a small correction expressed as the product of two thin matrices, `B × A`, whose shared inner dimension is the *rank* `r`. With `r=16`, a 2560×2560 layer is adjusted by two 2560×16 matrices, about 82,000 numbers instead of 6.5 million. The adapter learns the correction; the frozen base supplies everything else.

Adapters on the layers that matter. [`02_finetune_qlora.py:71-72`](02_finetune_qlora.py#L71-L72) attaches these to the seven projections in every transformer block, the four attention projections (`q`, `k`, `v`, `o`) and the three MLP ones (`gate`, `up`, `down`), across all 36 layers.

The measured result for this run:

| | |
|---|---|
| Trainable parameters | 33,030,144 |
| Share of the 4.02B base | 0.82% |
| Adapter on disk | 127 MB |
| Merged 4-bit GGUF | 2.4 GB |
| Training time, RTX 3070 Ti | 99 seconds, 60 optimiser steps |

Ninety-nine seconds. It is worth sitting with that number, because the mental model most people bring to "training a language model" is weeks and a cluster, and it makes them dismiss the technique before costing it. On a narrow classification task with a few hundred examples, fine-tuning is a coffee break, not a project. The expensive part of this example is not the training. It is writing the rulebook and labelling the data, which is exactly the part an actuary is qualified to do and cannot delegate.

## Step 1: the data, and the split that makes the number mean something

[`01_prepare_dataset.py`](01_prepare_dataset.py) turns the 200 synthetic notes in [`data/synthetic_claims.csv`](../data/synthetic_claims.csv) into three-turn chat records (system instruction, claim note, gold label as the assistant reply), and splits them 160/40.

Two design decisions carry all the weight.

The split is stratified and taken first. [`01_prepare_dataset.py:63-64`](01_prepare_dataset.py#L63-L64) removes exactly 8 notes per class before anything else happens, under the fixed seed at [`01_prepare_dataset.py:28`](01_prepare_dataset.py#L28). Stratification guarantees all five classes appear in the test set; taking it first guarantees the model never sees it. The docstring calls the test split *sacred*, and the word is chosen deliberately: the moment a test note leaks into training, every accuracy figure you quote becomes a measurement of memorisation. This is the same discipline as holding out an accident year to validate a reserving model, and it fails the same way: quietly, with flattering results.

The training system prompt is deliberately short. Compare the two prompts in the evaluator: the baseline at [`03_evaluate.py:29-43`](03_evaluate.py#L29-L43) carries the full rulebook with both tie-break rules; the fine-tuned one at [`03_evaluate.py:45-48`](03_evaluate.py#L45-L48) is a single sentence. Measured on this tokenizer, that is 143 tokens against 37, a 74 per cent reduction, 106 tokens saved on every call. Training uses the short form because teaching the rules to the weights is the entire point. If the fine-tuned model still needed the rulebook at inference, you would have gained nothing but a smaller file.

## Step 2: the training run, hyperparameter by hyperparameter

Everything sits in [`02_finetune_qlora.py:66-113`](02_finetune_qlora.py#L66-L113). What each setting does, and when to change it:

| Setting | Value | What it controls | When to change it |
|---|---|---|---|
| `r` | 16 | Adapter capacity. Higher fits more complex corrections and overfits sooner | 8 for a simpler task, 32 if loss plateaus high |
| `lora_alpha` | 16 | Scales the adapter's contribution; `alpha/r = 1` here | Leave it; move `r` instead |
| `lora_dropout` | 0.0 | Regularisation | Raise to 0.05 to 0.1 if you see overfitting |
| `target_modules` | 7 projections | Which matrices get adapters | Read the trap below before touching this |
| `num_train_epochs` | 3 | Passes over the 160 examples | More, on a tiny set, risks memorisation |
| `learning_rate` | 2e-4 | Step size. Two orders of magnitude above full fine-tuning, which is normal for LoRA | Halve it if loss oscillates |
| `per_device_train_batch_size` | 4 | Examples per forward pass, the VRAM lever | Halve on OOM, double the next row |
| `gradient_accumulation_steps` | 2 | Batches accumulated before an update; effective batch 8 | Inverse to the above |
| `optim` | `adamw_8bit` | 8-bit optimiser states, saving roughly 2 GB | Leave it |
| `use_gradient_checkpointing` | `"unsloth"` | Recomputes activations instead of storing them: slower, much less memory | Leave it |
| `seed` | 3407 | Reproducibility of shuffling and initialisation | Vary it deliberately; see below |

160 examples at an effective batch of 8 gives 20 steps per epoch and 60 in total, which is why the checkpoint directory is named `checkpoint-60`.

### Reading the loss correctly

The script prints `Training complete. Loss: 1.6810`, and that figure is the mean across the whole run, not the state you finished in. The last logged steps tell the real story:

| Epoch | Loss |
|---|---|
| 2.25 | 0.5377 |
| 2.50 | 0.4884 |
| 2.75 | 0.4575 |
| 3.00 | 0.3960 |

Still falling at the end. That is worth knowing and worth not over-reading: there is no validation loss in this pipeline, so a falling training loss is evidence of fitting, not of generalising. The held-out evaluation in step 3 is the only thing that distinguishes the two, which is why it is the deliverable rather than an afterthought.

## The trap: chat templates, and a model that looks trained but scores zero

This section exists because this pipeline failed in exactly this way, the failure is invisible from the loss curve, and nothing in the tooling warns you.

`Qwen3-4B-Instruct-2507` is a *non-thinking* model, but the chat template it ships still wraps every assistant turn in an empty reasoning block. Applied to the training data, each target became:

```
<|im_start|>assistant
<think>

</think>

PROPERTY_WATER<|im_end|>
```

The label is right there, so the data looks fine. The problem is `target_modules`: LoRA is attached to attention and MLP projections and not to `lm_head`, the output layer that turns hidden states into token probabilities. The training objective therefore demanded tokens the adapter had no mechanism to make more likely (`<think>` and `</think>` are ids 151667 and 151668, effectively dead in this checkpoint), so the model settled on the nearest ids it *could* reach: `<tool_call>` and `</tool_call>`, at 151657 and 151658. An off-by-ten in token space.

What came out of the served model:

```
'</tool_call>\n\n<tool_call>\n\nPROPERTY_FIRE'
```

The prediction is correct. The format is ruined. And because [`03_evaluate.py:58`](03_evaluate.py#L58) rejects any reply longer than 40 characters, every answer scored as invalid: 0/40 accuracy from a model that was classifying correctly underneath. The fix at [`02_finetune_qlora.py:81-90`](02_finetune_qlora.py#L81-L90) is one line: strip the empty block so the model trains on the bare label.

Three lessons generalise well beyond this repository:

1. Print your training text before you train. One `repr()` of the first formatted example would have shown this in seconds. Do it every time you change base model, template, or data format.
2. A chat template is part of the model contract, not a formatting detail. Templates ship with the weights, differ between a base model and its instruct variant, and change between releases.
3. A high invalid-output rate is a symptom to diagnose, never a parser to loosen. The tempting fix was to relax the 40-character guard, which would have produced a respectable accuracy figure from a model with no format discipline at all, precisely the property the fine-tune was supposed to deliver.

## Step 3: the evaluation, and the asymmetry that is the point

[`03_evaluate.py`](03_evaluate.py) runs both models over the same 40 unseen notes at `temperature=0`, and gives them deliberately unequal prompts: the rulebook to the baseline, one sentence to the fine-tuned model. That asymmetry is not a flaw in the comparison, it *is* the comparison. The question is not "which model is better on identical input" but "does putting the rules in the weights buy back what the smaller model gives up".

Measured result:

```
model                         accuracy   invalid
qwen3:8b                    38/40 (95%)         0
claims-classifier           38/40 (95%)         0
```

| | Prompted baseline | Fine-tuned |
|---|---|---|
| Parameters | 8B | 4B |
| Served size | 5.2 GB | 2.5 GB |
| System prompt | 143 tokens | 37 tokens |
| Accuracy | 38/40 (95%) | 38/40 (95%) |
| Invalid outputs | 0 | 0 |

The confusions differ, and the difference is the actuarially interesting part:

| Model | Error | Reading |
|---|---|---|
| `qwen3:8b` | `MOTOR_BI → LIABILITY_INJURY` and the reverse | The genuinely ambiguous boundary: injury on insured premises arising from a vehicle |
| `claims-classifier` | `MOTOR_BI → LIABILITY_INJURY` | Same boundary |
| `claims-classifier` | `PROPERTY_FIRE → PROPERTY_WATER` | Missed "origin governs": water used to extinguish a fire is a fire loss |

That second one is the finding worth acting on. It is not a random error; it is one of the two explicit tie-break rules from [example 02](../examples/02_claim_classification.md), and the model learned the other one (*injury outranks damage*) while under-learning this one. The diagnosis is straightforward: extinguishment and sprinkler cases are a slice of the roughly one-fifth of notes that are deliberately hard, so once the 40 test notes are removed there are only a handful left to learn from. If you extend the training set, extend it there: targeted examples on the rule you are getting wrong, not more notes in general.

## Reading the result honestly

Three cautions, in descending order of how often they are ignored.

Forty notes is a small test set. 38/40 is 95 per cent, and the Wilson 95 per cent confidence interval around it runs from 83.5 per cent to 98.6 per cent, over fifteen percentage points wide. Both models landing on 38/40 is *consistent with* parity and nowhere near *evidence* of it; on these numbers each model made one error the other did not, which no test can separate from noise. Quote the interval, or quote nothing.

This is one seed. [`02_finetune_qlora.py:109`](02_finetune_qlora.py#L109) fixes `seed=3407`, which makes the run reproducible but says nothing about variance. Training three adapters at different seeds and looking at the spread of held-out accuracy costs a few minutes of GPU time, and is the difference between "the fine-tune achieves 95 per cent" and "the fine-tune achieves 95 per cent ± something I have measured".

The classes are balanced and the data is synthetic. Forty test notes at eight per class is not your book. A classifier at 95 per cent on balanced classes can be worthless on a portfolio where one class is 2 per cent of volume, and template-generated notes lack the misspellings, pasted email chains and per-office conventions of real ones. Expect accuracy to fall and invalid rates to rise on real data, and note that the fine-tuned model, having been trained on the synthetic distribution, has more to lose from that shift than the prompted one does.

## What this example does not do

No validation split. 160 train, 40 test, nothing in between. Every hyperparameter judgement therefore has to be made against the test set, which slowly contaminates it. A real project holds out three ways.

No hyperparameter search. The values above are sensible defaults, not a tuned configuration.

No measurement of what was lost. Fine-tuning on one narrow task degrades unrelated capability: catastrophic forgetting. This adapter is measured only on the task it was trained for. If you intend to use the same model for anything else, measure that too, before and after.

No abstention. As in [example 02](../examples/02_claim_classification.md), the model returns a label, never "I am not sure". The invalid-output channel is the cheapest available proxy, and a fine-tune that drives invalid outputs to zero also removes that signal.

No drift monitoring. One run, one number, one day.

## The governance reading

Under ASOP 56 this is unambiguously a model, and fine-tuning raises the bar rather than lowering it: you are no longer merely a user of someone else's model, you have modified it, and the documentation burden moves accordingly.

An adapter is meaningless on its own. It reproduces only with the exact base model and the exact dataset that produced it. Record all three together (base model and revision, dataset version, adapter) in [`governance/model_card_template.md`](../governance/model_card_template.md), which has fields for each. An adapter file with no provenance is an unreviewable artefact, and it is far easier to produce one by accident here than with a prompt.

The training-data location rule is not negotiable. The Colab fallback in [`colab_finetune.ipynb`](colab_finetune.ipynb) is acceptable *only* because every example is synthetic. Training uploads your data to someone else's hardware and leaves it in their logs, caches and checkpoints. The moment the training set contains real claim notes, training happens on hardware you control. That rule is the thesis of this repository applied to the one step where people most often forget it, which is why [`01_prepare_dataset.py`](01_prepare_dataset.py) and the notebook both state it in their opening lines.

Against the NIST AI RMF, this example sits in MEASURE alongside example 02, and adds a MANAGE obligation the prompted pipeline does not have: a versioned artefact whose lineage must be maintained, re-evaluated when the base model changes, and retired deliberately. [Example 04](../examples/04_governance_wrapper.md) supplies the GOVERN and MAP side.

## Things to try

- Print the training text first. Add `print(repr(dataset[0]["text"]))` after the `map` at [`02_finetune_qlora.py:92`](02_finetune_qlora.py#L92) and read it. Then remove the `<think>` strip and print it again. Seeing both is the fastest inoculation against the trap above.
- Train three seeds. Change `seed` to 3408 and 3409, evaluate each, and look at the spread. This is the cheapest experiment here and it changes how you report every number.
- Cut the training set in half. 80 examples instead of 160. If accuracy barely moves, your task needs less data than you think, and the marginal labelling hour is better spent on the hard cases than on volume.
- Add examples for the rule the model missed. Write a dozen more fire-versus-water origin cases, retrain, and see whether that confusion disappears without introducing another. This is targeted data work, and it is the highest-value loop in the whole example.
- Give the fine-tuned model the full rulebook prompt. If accuracy does not improve, the rules really are in the weights. If it does, they are not, and you have learned something about how much training actually happened.
- Add `qwen3:4b` prompted as a third column. The comparison you want is not only 4B-tuned against 8B-prompted, but 4B-tuned against 4B-prompted, which isolates what the training contributed from what the size cost.
