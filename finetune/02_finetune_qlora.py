"""Fine-tune step 2: QLoRA training of Qwen3-4B on the claim notes.

What this does, in one paragraph: the 4B base model is loaded frozen in
4-bit, and small low-rank adapter matrices (well under 1% of the weights)
are trained on 160 labelled examples. The result is a ~100 MB adapter that
specialises the model for this one task. Training fits in roughly 8 GB of
GPU memory and takes minutes, not hours, on this dataset.

Requirements: an NVIDIA GPU (local, or a free Colab T4: see
colab_finetune.ipynb). Apple Silicon users: see the MLX path in README.md.

    pip install torch --index-url https://download.pytorch.org/whl/cu128
    pip install -r finetune/requirements.txt
    python finetune/01_prepare_dataset.py
    python finetune/02_finetune_qlora.py

Data note, consistent with the point of this repository: a hosted notebook
is acceptable here only because every training example is synthetic. The
moment the training set contains real data, training happens on hardware
you control, full stop.
"""

from pathlib import Path

from unsloth import FastLanguageModel   # first: Unsloth patches trl/transformers on import

from datasets import load_dataset
from trl import SFTConfig, SFTTrainer

REPO = Path(__file__).resolve().parents[1]
BASE_MODEL = "unsloth/Qwen3-4B-Instruct-2507"   # Apache 2.0
MAX_SEQ = 1024
OUT_DIR = REPO / "finetune" / "outputs"
QUANT = "q4_k_m"

# Ollama registration. Unsloth generates a Modelfile carrying the full
# thinking/tools template and, critically, no stop parameters, so Ollama
# never halts generation and the reply trails into the next turn's
# scaffolding. This is the minimal ChatML the Instruct model wants.
MODELFILE = '''FROM __GGUF__

TEMPLATE """{{- if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}
{{- range .Messages }}
{{- if eq .Role "user" }}<|im_start|>user
{{ .Content }}<|im_end|>
{{ end }}
{{- if eq .Role "assistant" }}<|im_start|>assistant
{{ .Content }}<|im_end|>
{{ end }}
{{- end }}<|im_start|>assistant
"""

PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
'''


def main() -> None:
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ,
        load_in_4bit=True,          # QLoRA: frozen 4-bit base
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=16,                        # adapter rank; 8-32 is the usual range
        lora_alpha=16,
        lora_dropout=0.0,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth",
        random_state=3407,
    )

    dataset = load_dataset(
        "json", data_files=str(REPO / "finetune" / "data" / "train.jsonl"),
        split="train")

    def format_chat(example):
        # Qwen3-Instruct-2507 is a non-thinking model, but the template it
        # ships still wraps every assistant turn in an empty <think></think>.
        # LoRA here trains no lm_head, so the model cannot learn to emit those
        # ids and settles on their neighbours (<tool_call>) instead, wrecking
        # format discipline. Train on the bare label.
        text = tokenizer.apply_chat_template(
            example["messages"], tokenize=False,
            add_generation_prompt=False)
        return {"text": text.replace("<think>\n\n</think>\n\n", "")}

    dataset = dataset.map(format_chat, remove_columns=dataset.column_names)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        args=SFTConfig(
            dataset_text_field="text",
            max_seq_length=MAX_SEQ,
            per_device_train_batch_size=4,
            gradient_accumulation_steps=2,   # effective batch 8
            num_train_epochs=3,
            learning_rate=2e-4,
            lr_scheduler_type="linear",
            warmup_steps=10,
            logging_steps=5,
            optim="adamw_8bit",
            seed=3407,
            output_dir=str(OUT_DIR / "checkpoints"),
            report_to="none",
        ),
    )
    stats = trainer.train()
    print(f"Training complete. Loss: {stats.training_loss:.4f}")

    # Save the adapter (small, portable, reviewable)...
    model.save_pretrained(str(OUT_DIR / "adapter"))
    tokenizer.save_pretrained(str(OUT_DIR / "adapter"))

    # ...and export a merged 4-bit GGUF that Ollama can serve directly.
    model.save_pretrained_gguf(
        str(OUT_DIR / "gguf"), tokenizer, quantization_method=QUANT)

    # Unsloth appends its own suffix to the export directory, so find the
    # artefact rather than assuming the path, and write our Modelfile over
    # the one it generated. Match the quantisation explicitly: the
    # intermediate BF16 export sorts ahead of it and is not always
    # cleaned up.
    gguf = sorted(OUT_DIR.glob(f"gguf*/*{QUANT.upper()}*.gguf"))[0]
    modelfile = gguf.parent / "Modelfile"
    modelfile.write_text(MODELFILE.replace("__GGUF__", gguf.name),
                         encoding="utf-8")

    print(f"Adapter and GGUF written under {OUT_DIR}")
    print("Register with Ollama:")
    print(f"  ollama create claims-classifier -f {modelfile}")


if __name__ == "__main__":
    main()
