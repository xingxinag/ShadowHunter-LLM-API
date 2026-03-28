# ShadowHunter-LLM-API

中文 | English

## 中文介绍

`ShadowHunter-LLM-API` 是一个基于 Streamlit 的大模型 API 审计工作台，用来把一个“自称是某模型”的目标接口，与一个可信的官方或参考接口进行对照审计。

它的核心目标很直接：

- 目标 API 是否真的在提供它声称的模型？
- 它是否只是影子 API、降级转发、代理包装，或者经过额外过滤的中间层？
- 在相同探针下，它和基线接口的行为到底有多接近？

当前仓库将这些问题落实成一个单进程、可视化、可复核的审计工具：输入基线与目标接口配置，运行多轮主动探针，对比相似度、置信度、漂移和原始响应。

## English Overview

`ShadowHunter-LLM-API` is a Streamlit-based audit workstation for comparing a claimed LLM API against a trusted baseline API.

Its purpose is simple:

- Does the target endpoint actually behave like the model it claims to expose?
- Is it a shadow API, downgraded relay, wrapper, or filtered proxy?
- Under the same probes, how close is its behavior to the baseline endpoint?

The current repository turns that into a practical, operator-facing workflow: configure baseline and target endpoints, run multi-round active probes, then inspect similarity, confidence, drift, and raw interactions in one place.

## Research Basis | 研究依据

This repository is explicitly grounded in the following three papers, which are also required references for this project:

- `https://arxiv.org/pdf/2407.15847` - `LLMmap: Fingerprinting For Large Language Models`
- `https://arxiv.org/abs/2508.09021` - `Attacks and Defenses Against LLM Fingerprinting`
- `https://arxiv.org/pdf/2603.01919v2` - `Real Money, Fake Models: Deceptive Model Claims in Shadow APIs`

中文说明：

- `2407.15847` 提供了主动式 LLM 指纹识别的核心思路，说明少量精心设计的交互就可以识别底层模型。
- `2508.09021` 讨论了指纹识别的攻防两端，包括更强的查询选择策略与对抗指纹识别的过滤方法。
- `2603.01919v2` 直接聚焦影子 API 的真实风险，说明虚假模型声明会破坏可靠性、可复现性与安全预期。

English note:

- `2407.15847` motivates active LLM fingerprinting with carefully selected prompts.
- `2508.09021` studies the attack-and-defense dynamics around fingerprinting.
- `2603.01919v2` highlights the real-world shadow API problem and why endpoint auditing matters.

## What The Current Code Actually Implements | 当前代码实际实现了什么

The current codebase is intentionally compact and auditable.

当前实现重点不是大规模分布式平台，而是一个可直接运行、容易检查代码逻辑的审计闭环。

- Single-process Streamlit application | 单进程 Streamlit 应用
- 8 probe dimensions, each built as a 3-turn conversation scaffold | 8 个探针维度，每个探针都是 3 轮对话结构
- Concurrent baseline/target execution for each probe | 每个探针会并发请求基线与目标接口
- Adaptive sampling up to 12 rounds when target-side instability remains high | 当目标端自距离过高时会自适应加采样，最高 12 轮
- Multimodal distance using lightweight text features plus Markdown structure overlap | 使用轻量文本特征和 Markdown 结构重叠计算多模态距离
- Summary metrics based on self-distance and cross-distance medians | 用自距离和跨端点距离的中位数计算核心指标
- Final verdicts: `VERIFIED`, `FRAUD DETECTED`, `INCONCLUSIVE` | 最终结论支持 `VERIFIED`、`FRAUD DETECTED`、`INCONCLUSIVE`
- UI panels for metrics, radar chart, heatmap, raw interactions, and error summaries | UI 中包含评分卡、雷达图、热力图、原始交互和错误摘要

Important / 说明：

Although `sentence-transformers`, `numpy`, and `scipy` appear in `requirements.txt`, the checked-in implementation in `core/distance.py` currently uses a lightweight local heuristic embedding rather than a transformer encoder.

虽然 `requirements.txt` 里包含 `sentence-transformers`、`numpy`、`scipy`，但当前仓库中的 `core/distance.py` 实际采用的是轻量启发式特征，而不是已经接入的 Transformer 向量模型。README 以当前代码状态为准，不把设计稿中的能力写成已落地功能。

## Audit Method | 审计方法

### 1. Active Probes | 主动探针

`core/probes.py` defines 8 dimensions / `core/probes.py` 当前定义了 8 个维度：

- metadata hallucination
- alignment boundary
- malformed syntax
- formatting quirks
- reasoning trap
- multilingual nuance
- coding style
- self identification

Each probe is sent as a 3-turn conversation / 每个探针都按 3 轮对话发送：

1. harmless setup prompt | 无害的上下文铺垫
2. bridge prompt | 收束上下文的桥接提示
3. final trap prompt | 最终的触发型探针

This structure is designed to make simple filtering or shallow prompt guards easier to observe.

这种结构的目的，是更容易观察那些仅靠浅层过滤、简单包装或二次转发维持一致性的接口。

### 2. Baseline vs Target Comparison | 基线与目标对比

`core/engine.py` collects probe responses across multiple rounds and computes:

- baseline self-distance | 基线自身波动
- target self-distance | 目标自身波动
- cross-distance | 基线与目标之间的跨端点偏差

The system summarizes these values with medians and derives the Cross/Self ratio.

系统会对这些距离分布取中位数，再计算 Cross/Self Ratio，用来区分“正常随机性”与“真正行为差异”。

### 3. Similarity and Confidence | 相似度与可信度

`core/statistics.py` exposes the main operator-facing metrics:

- `ratio`: `c_cross / (max(s_base, s_target) + 0.01)`
- `similarity`: exponential decay score derived from ratio
- `confidence`: success-rate-adjusted score penalized by unstable target behavior
- `verdict`: final audit label

对应中文理解：

- `ratio` 越高，说明目标响应相对基线偏离越大
- `similarity` 越低，说明目标越不像基线模型
- `confidence` 越低，说明这次审计虽然跑完了，但目标接口不稳定、失败率高，或自我波动太大
- `verdict` 是面向操作者的最终判断标签

### 4. Adaptive Sampling | 自适应采样

If the target endpoint remains highly unstable, the engine raises the round count until the target stabilizes or the run reaches 12 rounds.

如果目标接口自身波动持续偏高，系统会继续追加轮次，直到达到更稳定的统计结果，或者触达 12 轮上限。

## Supported Interface Types | 支持的接口类型

The gateway layer in `adapters/llm_gateway.py` currently supports:

- `openai_responses`
- `openai_compatible`
- `anthropic_messages`
- `amazon_bedrock`
- `gemini_native`
- `gemini_openai_compatible`

Implementation highlights / 实现细节：

- Locked sampling defaults for OpenAI-compatible paths to reduce noise | OpenAI 兼容路径默认锁定采样参数，减少噪声
- Direct `/responses` support with nested output parsing | 支持直接调用 `/responses` 并解析嵌套返回结构
- Fallback to `/chat/completions` on compatible-path failures | 兼容接口失败时可回退到 `/chat/completions`
- Manual request builders for Anthropic, Gemini native, and Bedrock | Anthropic、Gemini Native、Bedrock 使用手工构造请求
- SigV4 signing path for Bedrock | Bedrock 支持 SigV4 签名流程
- Bilingual error explanation in the UI | UI 内置双语错误解释

## UI Overview | 界面功能

`app.py` currently provides:

- bilingual UI (`zh` / `en`) | 中英文界面切换
- separate baseline and target credentials | 分离的基线与目标配置
- interface-specific runtime parameter inputs | 按接口类型展示参数输入项
- configurable sampling rounds | 可配置采样轮数
- metric cards for similarity, confidence, ratio, and feasibility | 相似度、可信度、比率、可行度评分卡
- radar chart for 8 probe dimensions | 8 维探针雷达图
- heatmap for cross-round distance drift | 跨轮次漂移热力图
- raw interaction review with filtering | 支持筛选的原始交互回看

The presentation layer is implemented in `ui/charts.py` and `ui/theme.py`.

图表与主题层分别在 `ui/charts.py` 和 `ui/theme.py` 中实现，整体风格更偏审计控制台而不是普通聊天前端。

## Repository Structure | 项目结构

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

## Installation | 安装

Recommended Python version / 建议 Python 版本：`3.11+`

```bash
pip install -r requirements.txt
```

## Run | 启动方式

```bash
streamlit run app.py
```

After launch, configure the following in the sidebar / 启动后在侧边栏配置：

- baseline API key and model | 基线 API Key 与模型
- target API key and model | 目标 API Key 与模型
- base URLs for both sides | 双方 Base URL
- interface type | 接口格式
- sampling rounds | 采样轮数
- provider-specific runtime options when needed | 按需填写特定厂商参数

## Environment Example | 环境变量示例

The repository includes `.env.example`:

```env
SHADOWHUNTER_BASELINE_API_KEY=replace-me
SHADOWHUNTER_TARGET_API_KEY=replace-me
SHADOWHUNTER_TARGET_BASE_URL=https://api.42w.shop/v1
SHADOWHUNTER_BASELINE_MODEL=gpt-5.2
SHADOWHUNTER_TARGET_MODEL=gpt-5.4-mini
```

`app.py` currently reads default model names and base URLs from environment variables, then allows overriding them in the UI.

`app.py` 当前会读取环境变量中的默认模型名和 Base URL，并允许你在界面中继续覆盖。

## Tests | 测试

```bash
python -m pytest tests -q
```

The tests currently cover / 当前测试覆盖：

- app defaults and bilingual labels | 默认表单状态和中英文文案
- provider parameter coverage | 各类供应商参数说明
- result shaping and error classification | 结果结构与错误分类
- adaptive engine behavior | 自适应采样引擎行为
- gateway request building and fallback paths | 网关请求构造与回退路径
- Responses, OpenAI-compatible, Anthropic, Gemini, and Bedrock handling | Responses、OpenAI Compatible、Anthropic、Gemini、Bedrock 的适配逻辑

## How To Read The Output | 如何理解结果

- High `similarity` + high `confidence` | 高相似度且高可信度：目标行为和基线接近，且统计过程稳定
- Low `similarity` | 低相似度：目标接口与基线存在明显行为偏差
- Low `confidence` | 低可信度：虽然运行结束，但目标端不稳定、报错多或波动过大
- `INCONCLUSIVE` | 结果不足以下结论，系统拒绝过度判断

This tool should be treated as an audit aid, not the sole source of truth.

这个工具更适合作为审计辅助系统，而不是唯一证据来源。涉及采购、合规、生产切换时，建议结合原始响应、接口日志和人工复核共同判断。

## Current Limitations | 当前限制

- The distance model is still lightweight and heuristic | 距离模型目前仍偏轻量、偏启发式
- Probe selection is static, not RL-optimized yet | 探针选择目前是静态的，还不是 RL 优化版
- The app is single-process, not a distributed audit service | 当前是单进程应用，不是分布式审计平台
- Thresholds are transparent but not calibrated for every provider family | 阈值逻辑透明，但还没有针对所有模型家族做细粒度标定
- Strong relays may require richer features and broader probe pools | 对于非常强的转发代理，可能需要更丰富的特征和更大的探针池

## Research Context | 研究背景链接

If you want to understand the research context behind this repository, start with these three required references:

- `https://arxiv.org/pdf/2407.15847`
- `https://arxiv.org/abs/2508.09021`
- `https://arxiv.org/pdf/2603.01919v2`

如果你希望先理解这个仓库背后的研究背景，也建议先读这 3 篇论文：它们分别覆盖了 LLM 指纹识别的基本方法、指纹识别的攻防关系，以及影子 API 的真实欺骗现状。
