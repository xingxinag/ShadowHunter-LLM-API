# ShadowHunter-LLM-API

`ShadowHunter-LLM-API` is a compact audit workstation for shadow LLM APIs. It compares a target endpoint against a trusted baseline endpoint under the same active probes, then reports how closely the target behaves like the claimed model.

The default repository README is Chinese. This file is the standalone English version.

## Problem Statement

Many third-party endpoints claim to expose official frontier models, while in practice they may be:

- downgraded models disguised as premium ones
- wrapper or relay layers in front of an official API
- filtered middle layers that rewrite outputs
- entirely different backends behind the same model name

This directly affects quality, stability, safety expectations, procurement decisions, and research reproducibility.

## Theoretical Basis

This project is explicitly grounded in three papers:

### 1. Active LLM fingerprinting

- `https://arxiv.org/pdf/2407.15847`
- `LLMmap: Fingerprinting For Large Language Models`

This paper shows that carefully designed active queries can identify underlying LLM versions even in black-box settings. It provides the conceptual foundation for the probe-and-compare workflow used here.

### 2. Fingerprinting as an attack-defense problem

- `https://arxiv.org/abs/2508.09021`
- `Attacks and Defenses Against LLM Fingerprinting`

This paper shows that fingerprinting is not static: attacks can become stronger, while defenses may try to obscure model identity through semantic-preserving filtering or rewriting. That is why this project emphasizes multi-round probing, raw-response review, and stability-aware scoring.

### 3. Real-world shadow API deception

- `https://arxiv.org/pdf/2603.01919v2`
- `Real Money, Fake Models: Deceptive Model Claims in Shadow APIs`

This paper focuses directly on deceptive shadow APIs and their real-world consequences. It motivates this repository as a practical audit tool rather than a toy model-identification demo.

## What The Current Code Implements

The repository implements a compact, inspectable audit loop rather than a distributed platform.

- single-process Streamlit application
- baseline vs target parallel comparison
- 8 probe dimensions
- 3-turn probe conversations
- multi-round sampling with adaptive extension up to 12 rounds
- self-distance, cross-distance, and Cross/Self ratio analysis
- final scores for similarity, confidence, and feasibility
- verdicts: `VERIFIED`, `FRAUD DETECTED`, `INCONCLUSIVE`
- UI panels for metrics, radar chart, heatmap, raw interactions, and error summaries

Important note: although `sentence-transformers`, `numpy`, and `scipy` are listed in `requirements.txt`, the checked-in implementation in `core/distance.py` currently uses lightweight heuristic text features and Markdown structural overlap instead of a transformer encoder.

## Audit Method

### 1. Active probes

`core/probes.py` currently defines 8 dimensions:

- metadata hallucination
- alignment boundary
- malformed syntax
- formatting quirks
- reasoning trap
- multilingual nuance
- coding style
- self identification

Each probe is structured as a 3-turn conversation:

1. setup prompt
2. bridge prompt
3. final trap prompt

### 2. Baseline-target comparison

`core/engine.py` collects:

- baseline self-distance
- target self-distance
- cross-endpoint distance

It summarizes these values with medians and derives the Cross/Self ratio.

### 3. Output metrics

`core/statistics.py` produces:

- `ratio`
- `similarity`
- `confidence`
- `verdict`

### 4. Adaptive sampling

If the target endpoint remains unstable, the engine increases the round count until the run stabilizes or reaches the 12-round cap.

## Supported Interface Types

`adapters/llm_gateway.py` currently supports:

- `openai_responses`
- `openai_compatible`
- `anthropic_messages`
- `amazon_bedrock`
- `gemini_native`
- `gemini_openai_compatible`

## UI Features

`app.py` currently provides:

- bilingual UI switching
- separate baseline and target configuration
- provider-specific runtime parameters
- sampling-round control
- metric cards
- probe radar chart
- cross-round heatmap
- raw interaction review and filtering

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
├── README.md
└── README_EN.md
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

## Tests

```bash
python -m pytest tests -q
```

## Interpreting Results

- high `similarity` + high `confidence`: target behavior is close to baseline and the run is stable
- low `similarity`: the target materially diverges from baseline behavior
- low `confidence`: the run completed, but the target was unstable or error-prone
- `INCONCLUSIVE`: the system refuses to overclaim under weak evidence

## Current Limitations

- the distance model is still lightweight and heuristic
- probe selection is static rather than RL-optimized
- the app is single-process, not a distributed audit service
- thresholds are transparent but not calibrated for every provider family
- stronger relay layers may require richer features and a broader probe pool
