# ShadowHunter-X

ShadowHunter-X is a Streamlit-based single-process audit workstation for detecting shadow LLM APIs through active probing and Cross/Self Ratio statistics.

## Stack

- Python 3.11+
- Streamlit
- streamlit-echarts
- LiteLLM
- sentence-transformers
- numpy
- scipy
- tenacity

## Structure

- `app.py`: Streamlit entrypoint
- `core/engine.py`: async audit orchestration
- `core/probes.py`: 8-dimension probes and three-turn traps
- `core/distance.py`: semantic and structural distance logic
- `core/statistics.py`: ratio, similarity, confidence, adaptive sampling
- `adapters/llm_gateway.py`: LiteLLM unified gateway
- `ui/charts.py`: ECharts option builders
- `ui/theme.py`: cyber-audit CSS injection

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Test

```bash
python -m pytest tests -q
```
