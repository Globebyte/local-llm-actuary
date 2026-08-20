# Fine-tuning: when prompting is not enough

Companion explainer: [`fine_tuning_explained.md`](fine_tuning_explained.md) walks through the whole recipe for actuaries rather than developers: what QLoRA does and what it costs, every hyperparameter and when to change it, the chat-template trap that silently produces a model scoring 0/40 while classifying correctly underneath, how to read the measured results honestly, and where the approach falls short. Read it alongside the three scripts.

## Why fine-tune at all

Prompting gets you a long way, and you should exhaust it first: it is faster, reversible, and model-agnostic. Fine-tune when you hit one of these walls:

1. Format discipline. You need exactly one label, every time, parseable by code, and the prompted model still occasionally editorialises.
2. Domain vocabulary. Your notes are full of shorthand (FNOL, EL/PL, NSD, insd) and house conventions that a general model half-understands.
3. Economics. A small model fine-tuned on your narrow task can match or beat a much larger prompted one, while running faster on smaller hardware. That changes what is feasible on a standard corporate laptop.

## What QLoRA actually is

Not retraining. The base model stays frozen, compressed to 4-bit; you train small low-rank adapter matrices, well under one per cent of the total weights. The output is a ~130 MB adapter file plus, if you want it, a merged GGUF you can serve from Ollama like any other model. On this dataset (160 training examples), the whole run fits in roughly 8 GB of GPU memory and completes in minutes.

## The three steps

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128  # CUDA, not PyPI's CPU wheel
pip install -r finetune/requirements.txt      # NVIDIA GPU path
python finetune/01_prepare_dataset.py         # 160 train / 40 held-out test
python finetune/02_finetune_qlora.py          # QLoRA on Qwen3-4B, exports GGUF
ollama create claims-classifier -f finetune/outputs/gguf_gguf/Modelfile
python finetune/03_evaluate.py --models qwen3:8b claims-classifier
```

The evaluation is the deliverable: same 40 unseen notes, prompted 8B versus fine-tuned 4B, accuracy and invalid-output rate side by side. Note the asymmetry: the baseline gets the full rulebook prompt, the fine-tuned model gets a one-line instruction, because the rules now live in the weights.

## Hardware paths

- Local NVIDIA GPU (primary). 8 GB VRAM upwards, and it has to be 8 GB *free*: a browser and a video-call app can hold several GB between them, so check `nvidia-smi` before blaming the script. Install torch from the PyTorch CUDA index, not PyPI, or Unsloth aborts with "cannot find any torch accelerator". If memory is still tight, halve `per_device_train_batch_size` and double `gradient_accumulation_steps` for the same effective batch.
- Free Colab T4 (fallback). `colab_finetune.ipynb` runs the same three steps end to end. Acceptable here only because the data is synthetic: the moment your training set contains real claims, training happens on hardware you control. That rule is the thesis of the whole repository applied to training.
- Apple Silicon (MLX). Unsloth is CUDA-only. On a Mac, use Apple's MLX-LM, which trains LoRA adapters natively on unified memory. `01_prepare_dataset.py` already writes MLX-format splits:

  ```bash
  pip install mlx-lm
  mlx_lm.lora --model Qwen/Qwen3-4B-Instruct-2507 --train \
      --data finetune/data/mlx --iters 300 --batch-size 4
  mlx_lm.generate --model Qwen/Qwen3-4B-Instruct-2507 \
      --adapter-path adapters --prompt "<claim note here>"
  ```

  MLX serves the adapter for evaluation via `mlx_lm.server` (OpenAI-compatible, port 8080), so `03_evaluate.py` works with `LLM_BASE_URL=http://localhost:8080/v1`. Fusing and converting MLX adapters to GGUF is possible but fiddlier; if your deployment target is Ollama, the CUDA path is smoother end to end.

## Data discipline

- The test split is stratified, held out before training, and never trained on. Every accuracy claim comes from it.
- Track your dataset version alongside the adapter: an adapter is only meaningful with the data and base model that produced it. The model card template in `governance/` has fields for all three.
- 160 examples is deliberately small and it works for a five-class, well-specified task. Quality and label consistency beat volume; if accuracy disappoints, fix the labelling rules before adding data.

---

For help, assistance, or more information: [globebyte.com](https://globebyte.com/)
