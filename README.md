# ShadowHunter-LLM-API

`ShadowHunter-LLM-API` is a Streamlit-based audit workstation for comparing a claimed LLM API against a trusted baseline API through active probing, multi-round sampling, and Cross/Self ratio analysis.

The project is built for a practical question: when a third-party endpoint claims it is serving a frontier model, does its behavior actually look like the official model, or is it a shadow API, wrapper, downgraded backend, or filtered relay?

## Why This Project Exists

This repository is directly motivated by three lines of recent research:

- `https://arxiv.org/pdf/2407.15847` - `LLMmap: Fingerprinting For Large Language Models` introduces active fingerprinting with carefully chosen prompts and shows that a small number of interactions can identify underlying models with high accuracy.
- `https://arxiv.org/abs/2508.09021` - `Attacks and Defenses Against LLM Fingerprinting` studies both stronger fingerprinting strategies and practical defenses, including reinforcement-learning-optimized query selection and semantic-preserving output filtering.
- `https://arxiv.org/pdf/2603.01919v2` - `Real Money, Fake Models: Deceptive Model Claims in Shadow APIs` documents the real-world shadow API problem and shows that deceptive model claims can materially affect reliability, safety behavior, and research validity.

ShadowHunter turns that research direction into an operator-facing tool: enter a baseline endpoint and a target endpoint, run the same probe set against both, then inspect similarity, confidence, drift, and raw interactions in one place.

## What The Current Code Implements

The current implementation focuses on a compact, inspectable audit loop rather than a large distributed platform.

- Runs inside a single Python process with Streamlit as both UI and orchestration shell.
- Uses 8 probe dimensions, each expressed as a 3-turn conversation scaffold.
- Sends the same probes to baseline and target endpoints concurrently.
- Supports adaptive sampling from the requested round count up to 12 rounds when target-side self-distance stays high.
- Computes a multimodal distance from:
  - lightweight text-embedding-style features (`length`, `unique tokens`, `code fence count`)
  - Markdown structural tag overlap
- Derives summary metrics from median self-distance and cross-distance.
- Classifies the final verdict as `VERIFIED`, `FRAUD DETECTED`, or `INCONCLUSIVE`.
- Surfaces raw probe dialogs, error summaries, radar data, and a cross-round heatmap in the UI.

Important: the repository includes `sentence-transformers`, `numpy`, and `scipy` in `requirements.txt`, but the current checked-in distance implementation in `core/distance.py` uses a lightweight local heuristic embedding, not a transformer encoder. The README reflects the code as it exists today.

## Audit Method

### 1. Active probes

`core/probes.py` defines 8 dimensions:

- metadata hallucination
- alignment boundary
- malformed syntax
- formatting quirks
- reasoning trap
- multilingual nuance
- coding style
- self identification

Each probe is sent as a 3-turn conversation:

1. harmless setup prompt
2. bridge prompt that narrows the frame
3. final trap prompt that exposes behavioral quirks

This matches the repository's practical goal: reduce simple prompt-filter evasion and inspect how the endpoint behaves under controlled but varied stress.

### 2. Baseline vs target comparison

`core/engine.py` collects probe responses for both endpoints across multiple rounds:

- baseline self-distance: how much the trusted endpoint varies with itself
- target self-distance: how much the audited endpoint varies with itself
- cross-distance: how far target responses drift from baseline responses

The engine then summarizes those distributions with medians and computes the Cross/Self ratio.

### 3. Similarity and confidence

`core/statistics.py` turns the raw distances into operator-facing metrics:

- `ratio`: `c_cross / (max(s_base, s_target) + 0.01)`
- `similarity`: an exponential decay score derived from the ratio
- `confidence`: success-rate-adjusted score penalized by unstable target self-distance
- `verdict`:
  - `VERIFIED` when similarity is high enough
  - `FRAUD DETECTED` when similarity drops below threshold
  - `INCONCLUSIVE` when failures dominate and the run is not trustworthy

### 4. Adaptive rounds

If target self-distance remains high, the engine increases the sampling round count until the target stabilizes or the run reaches 12 rounds. This makes unstable endpoints easier to flag without requiring the operator to guess the right round count up front.

## Supported API Interface Types

The gateway layer in `adapters/llm_gateway.py` supports several interface styles:

- `openai_responses`
- `openai_compatible`
- `anthropic_messages`
- `amazon_bedrock`
- `gemini_native`
- `gemini_openai_compatible`

Notable implementation details:

- OpenAI-compatible paths use locked sampling defaults to reduce noise.
- `openai_responses` can call `/responses` directly and parses nested output payloads.
- OpenAI-compatible failures can fall back to `/chat/completions`.
- Anthropic, Gemini native, and Bedrock requests are constructed manually.
- Bedrock signing is supported through SigV4 when credentials are supplied.
- Error messages are normalized in the UI into bilingual operator guidance.

## UI Overview

The Streamlit app in `app.py` provides:

- bilingual UI (`zh` / `en`)
- separate baseline and target credentials
- interface-specific runtime parameter inputs
- adjustable sampling rounds
- result cards for similarity, confidence, ratio, and feasibility
- radar chart for 8 probe dimensions
- heatmap for cross-round distance drift
- raw interaction review with error-state filtering

The visual layer lives in `ui/charts.py` and `ui/theme.py` and is tuned for an audit-console workflow rather than a generic chat UI.

## Repository Structure

```text
ShadowHunter-LLM-API/
├── app.py
├── adapters/
│   └── llm_gateway.py
├── core/
│   ├── distance.py
│   ├── engine.py
│   ├── probes.py
│   └── statistics.py
├── docs/
├── tests/
├── ui/
│   ├── charts.py
│   └── theme.py
├── .env.example
├── requirements.txt
└── README.md
```

## Installation

Recommended Python version: `3.11+`

```bash
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

After launch, configure:

- baseline API key and model
- target API key and model
- base URLs for both sides
- interface type
- sampling rounds
- provider-specific runtime options when needed

Then start the audit from the sidebar.

## Environment Example

The repository includes `.env.example`:

```env
SHADOWHUNTER_BASELINE_API_KEY=replace-me
SHADOWHUNTER_TARGET_API_KEY=replace-me
SHADOWHUNTER_TARGET_BASE_URL=https://api.42w.shop/v1
SHADOWHUNTER_BASELINE_MODEL=gpt-5.2
SHADOWHUNTER_TARGET_MODEL=gpt-5.4-mini
```

`app.py` currently reads default base URLs and model names from environment variables, then lets the operator override them in the UI.

## Tests

Run the test suite with:

```bash
python -m pytest tests -q
```

The tests cover:

- default app state and bilingual labels
- provider-specific parameter coverage
- result card shaping and error classification
- adaptive engine behavior and inconclusive runs
- gateway payload construction and fallback behavior
- Bedrock, Gemini, Anthropic, Responses, and OpenAI-compatible request handling

## How To Read The Output

- High `similarity` + high `confidence`: target behavior is close to the baseline and the run was stable.
- Low `similarity`: target behavior diverges materially from the baseline.
- Low `confidence`: the run completed, but the target was unstable, error-prone, or highly inconsistent.
- `INCONCLUSIVE`: failures dominate enough that the system refuses to overclaim.

This tool is best used as an audit aid, not as a sole source of truth. Raw interactions should always be reviewed before making production or procurement decisions.

## Current Limitations

- The distance model is intentionally lightweight and heuristic in the current codebase.
- Probe selection is static; it is not yet RL-optimized.
- The app is a single-process operator console, not a distributed audit service.
- Verdict thresholds are simple and transparent, but not calibrated for every provider family.
- A sophisticated relay that heavily rewrites outputs may require a richer feature extractor and broader probe pool.

## Research Context

If you are evaluating whether an endpoint is an authentic model service or a deceptive proxy, start with the three papers that shaped this repository:

- `https://arxiv.org/pdf/2407.15847`
- `https://arxiv.org/abs/2508.09021`
- `https://arxiv.org/pdf/2603.01919v2`

They cover the core fingerprinting idea, the attack/defense dynamics around fingerprinting, and the real-world shadow API ecosystem that makes this kind of auditing necessary.
