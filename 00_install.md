# Install guide

Target: a working local model, callable from Python, in about thirty minutes on an ordinary machine. Two on-ramps are covered: Ollama (command line, scriptable, what every example in this repository uses) and LM Studio (a graphical alternative if you want to browse and chat before writing any code).

## Hardware expectations

| Tier | Typical machine | What runs comfortably |
|---|---|---|
| Entry | 16 GB RAM laptop, no discrete GPU | 4B-class models, quantised; fine for learning and the examples here at reduced speed |
| Demo | 8 to 12 GB VRAM GPU, RTX 3060 to 3080 class | 8B-class models at 4-bit; everything in this repository, quick enough to demonstrate live but slowing as the context grows |
| Anchor | Mac with 32 to 64 GB unified memory, or a Windows/Linux box with a 16 to 24 GB VRAM GPU | 8B to 14B-class models at comfortable speed; everything in this repository |
| Workstation | 96 GB+ unified memory or multi-GPU | 30B-class mixture-of-experts models and beyond |

Two rules of thumb: memory is the binding constraint, not raw speed; and a 4-bit quantisation of a model needs roughly 0.6 to 0.7 GB per billion parameters, plus working room.

## 1. Install Ollama

### macOS

```bash
brew install ollama          # or download the app from ollama.com
ollama serve                 # if installed via brew; the app starts it for you
```

### Windows

Download and run the installer from ollama.com, or `winget install Ollama.Ollama`. This is a per-user install needing no administrator rights, and Ollama then runs as a background service.

Open a new terminal afterwards. The installer extends `PATH` for new processes only, so shells that were already running will insist `ollama` is not recognised.

A new tab is not always enough. An editor's integrated terminal inherits the environment from the editor process rather than reading `PATH` afresh, so if VS Code was open when you installed, every terminal it spawns keeps the old `PATH` until you quit VS Code completely: all windows, not just the current one. To carry on in the shell you already have:

```powershell
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
```

### Linux, including WSL

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

The installer ships its payload zstd-compressed, and minimal images (Ubuntu under WSL among them) do not include the `zstd` binary. If the script stops with *This version requires zstd for extraction*, install it and rerun:

```bash
sudo apt update && sudo apt install -y zstd
```

Two things worth knowing under WSL. The installer registers Ollama as a systemd service, which needs `systemd=true` under `[boot]` in `/etc/wsl.conf` (on by default in recent WSL; `wsl --shutdown` after changing it). And an NVIDIA GPU is already visible to the distro through the Windows driver (check for `/dev/dxg` and working `nvidia-smi`), so do not install a Linux NVIDIA driver inside WSL.

Verify: `ollama --version`.

## 2. Pull the models

```bash
ollama pull qwen3:8b            # ~5 GB, Apache 2.0, the default for this repo
ollama pull nomic-embed-text    # small local embedding model, used by example 03
```

First chat, straight from the terminal:

```bash
ollama run qwen3:8b
```

Type a question; `/bye` to exit. If this works, the hard part is over.

The two models above need about 5.5 GB, landing in `%USERPROFILE%\.ollama\models` on Windows and `~/.ollama/models` elsewhere. If your system drive is tight, point `OLLAMA_MODELS` at somewhere roomier before pulling.

Tight on memory? `ollama pull qwen3:4b` and set `LLM_MODEL=qwen3:4b` when running the examples. Everything in this repository works on the 4B model, a little less capably.

## 3. Python environment

```bash
git clone https://github.com/globebyte/local-llm-actuary.git
cd local-llm-actuary
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Two Windows corrections to that block. `source` is a shell builtin that PowerShell does not have, and a virtual environment on Windows puts its scripts in `.venv\Scripts`, not `.venv/bin`, so use the commented form. And run the lines separately: `&&` chaining is a parse error in Windows PowerShell 5.1, which is what `powershell.exe` still gives you. Use `;` if you want them on one line.

## 4. Verify

```bash
python examples/01_first_query.py
```

You should get a three-sentence explanation of IBNR, from a model running entirely on your machine. Unplug the network and run it again if you want to enjoy the point.

## The LM Studio alternative

If you would rather start with a graphical application: install LM Studio from lmstudio.ai, use its built-in browser to download a Qwen3 8B build, and chat in the app. When you are ready for the examples, start LM Studio's local server (Developer tab); it serves the same OpenAI-compatible API on port 1234, so the repository works with two environment variables:

```bash
export LLM_BASE_URL=http://localhost:1234/v1
export LLM_MODEL=<model name as shown in LM Studio>
```

## Troubleshooting

- `Connection refused`: the server is not running. `ollama serve` (or start the desktop app / LM Studio server) and retry.
- `This version requires zstd for extraction`: the Linux install script cannot unpack its bundle. `sudo apt update && sudo apt install -y zstd`, then rerun the script. Having GNU `tar` is not sufficient: it delegates zstd handling to the same binary.
- `ollama` not recognised immediately after installing on Windows: the install worked; your shell predates it. Confirm with `& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" --version`. If that answers, it is purely a `PATH` refresh, so quit VS Code entirely or use the one-liner in the Windows install section above.
- `The term 'source' is not recognized`, or `The token '&&' is not a valid statement separator`: you are running the macOS/Linux lines in PowerShell. Activate with `.venv\Scripts\Activate.ps1` and issue the commands on separate lines.
- `Activate.ps1 cannot be loaded because running scripts is disabled`: PowerShell's execution policy. `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use `.venv\Scripts\activate.bat` from `cmd.exe` instead.
- `pip install` hangs or crawls: check `pip config list` for an `extra-index-url`: an internal or vendor mirror that no longer resolves costs several retries per package. `pip install --index-url https://pypi.org/simple -r requirements.txt` sidesteps it.
- Painfully slow: the model is bigger than your memory and is swapping. Drop to `qwen3:4b`, or close the things eating your RAM.
- Different port or remote machine: set `LLM_BASE_URL` accordingly; the examples read it.
- Corporate laptop, no admin rights: LM Studio's per-user install sometimes succeeds where system installers cannot; failing that, this is a conversation with IT that the governance folder is designed to help you win.
