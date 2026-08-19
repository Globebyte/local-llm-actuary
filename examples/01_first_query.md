# Example 01: the OpenAI-compatible bridge

Script: [`01_first_query.py`](01_first_query.py) · Practice area: any · Run: `python examples/01_first_query.py`

## What this example is for

It answers one question: what has to change in your Python when the model stops being a service you call over the internet and becomes a process on your own machine?

The answer is one line. That is the whole point of the example, and it is worth more than it first appears, because it determines how much of your existing work survives the move. If adopting a local model meant rewriting every integration, most teams would never get past the pilot. It does not.

## The mechanism

Ollama serves two APIs at once. Its own native API lives at `/api/...` on port 11434, and alongside it sits an OpenAI-compatible surface at `/v1/...` that speaks the same request and response shapes as `api.openai.com`. Any client library that can be pointed at a different base URL will talk to it: the official `openai` package, LangChain, LlamaIndex, or your own `requests` code.

So the migration is a change of address:

```python
client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
```

Everything downstream (`client.chat.completions.create(...)`, the `messages` list with its system and user roles, `response.choices[0].message.content`) is unchanged from cloud code. [`01_first_query.py:23-24`](01_first_query.py#L23-L24) is the entire difference.

### The api_key that is not a key

`api_key="ollama"` looks like a placeholder because it is one. The `openai` client refuses to construct without a key, so a value must be supplied; Ollama then ignores it. Any string works: I confirmed `"literally-anything"` is accepted and served normally. This matters for a practical reason: there is no secret in this code path, nothing to rotate, and nothing to leak into a repository. It also matters as a caution, because it means the local endpoint has no authentication of its own. If you bind Ollama to anything other than localhost, anyone who can reach the port can use your model. That is a network decision, not an application one.

### Reading the environment rather than hard-coding

Both the base URL and the model name come from environment variables with defaults:

```python
client = OpenAI(base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"), ...)
MODEL = os.getenv("LLM_MODEL", "qwen3:8b")
```

Every example in the repository follows this convention, which is why the same scripts run unchanged against LM Studio on port 1234, against a colleague's workstation, or against a smaller model on a memory-constrained laptop. It costs two lines and removes the most common reason people fork a script.

## The settings, and what they do and do not buy you

```python
temperature=0,   # deterministic-leaning
seed=42,         # fixed sampling seed
```

`temperature` controls how much randomness enters token selection. At 0 the model takes the highest-probability token at each step rather than sampling from the distribution. `seed` fixes the pseudo-random draw for any sampling that remains. Together they make output *far* more stable between runs, which is what you want for anything you intend to measure or reproduce.

They do not make it identical. This distinction is worth internalising before you promise reproducibility to anyone:

- Floating-point arithmetic is not associative. GPU kernels sum partial products in whatever order the hardware schedules them, and a different order gives a very slightly different result. Occasionally that difference is enough to flip which token ranks highest.
- Batching changes the arithmetic. The same prompt evaluated alone and evaluated alongside other requests can take different code paths.
- Runtime and quantisation are part of the model. A newer Ollama build, a different GGUF quantisation of the same weights, or different offload between GPU and CPU can all change output.

The practical consequence, and the reason [example 04](04_governance_wrapper.md) exists: *the log, not the settings, is what makes a run auditable.* If you need to show later what the model said, record what it said. Do not rely on being able to re-derive it.

## Two Qwen3-specific details

`qwen3:8b` is a hybrid reasoning model: it can emit an internal deliberation inside `<think>...</think>` tags before its actual answer. That is useful for hard reasoning and unhelpful for anything you intend to parse. The example handles it twice over:

1. `/no_think` in the system prompt is a soft switch asking the model not to produce the block. Models that do not recognise it simply ignore the token.
2. `strip_think()` at [`01_first_query.py:29-36`](01_first_query.py#L29-L36) removes any block that appears anyway.

Belt and braces, deliberately. The soft switch is a request, not a guarantee, and a stray `<think>` block in the middle of a parsed field is exactly the kind of failure that shows up in production and not in testing. Defending against it costs one regular expression.

## What to look at when you run it

You should get three sentences on IBNR. The content is unremarkable; four other things are worth noticing.

Latency and where it goes. The first call after a cold start is slow because the weights are being read from disk into memory. Subsequent calls are much faster. Ollama keeps the model resident for a few minutes of idleness and then releases the memory, so an occasional slow call in a long session is expected behaviour rather than a fault.

Where the work happens. Watch GPU memory (`nvidia-smi`, or Activity Monitor on a Mac) while the call runs. On an 8 to 12 GB card a 4-bit 8B model sits comfortably in VRAM. If you see it spill to system RAM, you are in the regime where the model is bigger than the memory you gave it, and the honest fix is a smaller model rather than patience.

That the network is irrelevant. Disconnect it and run the example again. This is the demonstration that matters to a compliance conversation: the trust boundary is your machine, and it can be shown rather than asserted.

That the answer is plausible and unverified. The model produced a competent description of IBNR because IBNR is well represented in its training data. Nothing in this example checks it. That gap is the subject of the next three examples.

## How this maps to real work

The reason this example is first is that it identifies the correct unit of change. Teams that have already built something against a cloud API (a drafting assistant, a summariser, a triage prototype) usually assume that moving to a local model means starting again, and they are usually wrong. The prompt engineering transfers. The parsing transfers. The tests transfer. What changes is the base URL, the model's capability, and the governance story, in that order of effort and reverse order of importance.

The capability change is real and should not be glossed over. An 8B model is not a frontier model. On open-ended reasoning across long context it will lose, sometimes badly. On narrow, well-specified tasks with a clear output contract, which is what most automatable actuarial work looks like, the gap narrows sharply, and the remaining three examples are built around tasks of that shape.

## Things to try

- Set `LLM_MODEL=qwen3:4b` and compare the answer. The 4B model is noticeably terser and occasionally less precise; whether that matters depends entirely on the task.
- Raise `temperature` to 0.8 and run the same prompt five times. This is the fastest way to build an intuition for what temperature actually controls, and for why anything you intend to measure should run at 0.
- Delete `/no_think` from the system prompt and print the raw response before `strip_think` touches it. Seeing the reasoning block is instructive, and so is seeing how much longer the call takes.
- Ask something the model cannot know, such as a figure from your own reserving basis. It will produce a confident, well-formed, wrong answer. That is confabulation, the failure mode [example 03](03_methodology_qa.md) is built to control.
