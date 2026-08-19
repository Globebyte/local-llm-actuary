"""Regenerates colab_finetune.ipynb from the three fine-tune scripts.

Run after editing any of the numbered scripts so the notebook stays in sync:
    python finetune/build_colab_notebook.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def md(text):
    return {"cell_type": "markdown", "metadata": {},
            "source": text.splitlines(keepends=True)}


def code(text):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": text.splitlines(keepends=True)}


cells = [
    md("# Fine-tune a local claims classifier (QLoRA, free Colab T4)\n\n"
       "End-to-end run of the `local-llm-actuary` fine-tuning recipe on a free "
       "Colab GPU.\n\n**Runtime > Change runtime type > T4 GPU** before "
       "running.\n\n**Data rule:** this notebook is acceptable on hosted "
       "compute only because every training example is synthetic. With real "
       "data, train on hardware you control."),
    code("!nvidia-smi\n"),
    code("!pip install -q unsloth transformers trl datasets peft bitsandbytes\n"),
    code("!git clone https://github.com/globebyte/local-llm-actuary.git\n"
         "%cd local-llm-actuary\n"),
    md("## 1. Prepare the dataset (160 train / 40 held-out test)"),
    code("!python finetune/01_prepare_dataset.py\n"),
    md("## 2. Train (QLoRA on Qwen3-4B) and export GGUF\n\nMinutes on a T4 "
       "for this dataset."),
    code("!python finetune/02_finetune_qlora.py\n"),
    md("## 3. Download the artefacts\n\nFetch the zip, then on your own "
       "machine, from a clone of this repository:\n\n```\nunzip "
       "finetuned_model.zip\npython finetune/01_prepare_dataset.py\n"
       "ollama create claims-classifier -f "
       "finetune/outputs/gguf_gguf/Modelfile\npython finetune/03_evaluate.py "
       "--models qwen3:8b claims-classifier\n```\n\nStep 1 is rerun locally "
       "because the split files are not committed. Its fixed seed reproduces "
       "the identical 40-note test set, which is what makes the comparison "
       "against the prompted baseline meaningful."),
    code("from google.colab import files\nimport glob\n"
         "for f in glob.glob('finetune/outputs/gguf_gguf/*'):\n"
         "    print(f)\n"
         "# files.download(<path>)  # uncomment per file, or zip the folder:\n"
         "!zip -r -q finetuned_model.zip finetune/outputs/gguf_gguf\n"
         "files.download('finetuned_model.zip')\n"),
]

for i, cell in enumerate(cells):
    cell["id"] = f"cell-{i}"          # required from nbformat 4.5

nb = {"nbformat": 4, "nbformat_minor": 5,
      "metadata": {"colab": {"provenance": [], "gpuType": "T4"},
                   "kernelspec": {"name": "python3", "display_name": "Python 3"},
                   "accelerator": "GPU"},
      "cells": cells}

out = HERE / "colab_finetune.ipynb"
out.write_text(json.dumps(nb, indent=1), encoding="utf-8")
print(f"Wrote {out}")
