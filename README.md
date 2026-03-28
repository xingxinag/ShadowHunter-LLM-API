# ShadowHunter-LLM-API

`ShadowHunter-LLM-API` 是一个面向影子大模型接口审计的单体化工作台，用于把“目标 API”与“可信基线 API”放在同一组主动探针下做并行对照，从而判断目标接口是否真的提供其声称的模型能力。

默认文档为中文版；英文版请见 `[ShadowHunter-LLM-API 英文说明文档](https://github.com/xingxinag/ShadowHunter-LLM-API/blob/main/README_EN.md)`。

## 项目要解决什么问题

在实际使用中，很多第三方接口会声称自己提供某个官方大模型，但真实情况可能是：

- 降级模型冒充高价模型
- 套壳代理转发为官方接口
- 多层中转后输出被二次过滤或改写
- 同名模型背后实际接的是完全不同的底座

这类“影子 API”会直接影响：

- 业务效果与稳定性
- 安全策略一致性
- 成本与采购判断
- 学术实验与评测的可复现性

本项目的目标，就是把这类问题变成一个可以重复执行、可视化查看、可人工复核的审计流程。

## 项目理论依据

本项目不是凭经验拍脑袋设计的，而是明确建立在以下 3 篇论文的思路之上：

### 1. LLM 主动指纹识别

- `https://arxiv.org/pdf/2407.15847`
- 论文：`LLMmap: Fingerprinting For Large Language Models`

这篇论文说明：即使只能黑盒访问一个大模型应用，只要设计足够有辨识度的查询，就能在少量交互中识别底层模型版本。它提供了“主动探针 + 响应对比”的核心思想，也是本项目探针审计方法的理论起点。

### 2. 指纹识别的攻防关系

- `https://arxiv.org/abs/2508.09021`
- 论文：`Attacks and Defenses Against LLM Fingerprinting`

这篇论文进一步说明，指纹识别不是静态问题，而是攻防对抗问题。一方面，查询可以被优化得更强；另一方面，影子 API 或代理层也可能通过二次模型过滤、语义保持改写等方式来掩盖自身身份。这也是为什么本项目强调多轮探针、原始响应复核和稳定性评估，而不是只看单次输出。

### 3. 影子 API 的现实危害

- `https://arxiv.org/pdf/2603.01919v2`
- 论文：`Real Money, Fake Models: Deceptive Model Claims in Shadow APIs`

这篇论文直接聚焦“影子 API”现象本身，指出虚假模型声明会破坏可靠性、安全性、研究有效性与用户利益。它为本项目提供了明确的问题背景：我们不是单纯做模型趣味识别，而是在做面向真实风险的接口审计。

## 当前代码实际实现了什么

当前仓库实现的是一个紧凑、可落地、易检查代码逻辑的审计闭环，而不是复杂的分布式平台。

### 已实现能力

- 基于 Streamlit 的单进程审计工作台
- 基线接口与目标接口并行对照
- 8 个探针维度的主动查询
- 每个探针采用 3 轮对话结构
- 多轮采样与目标侧自适应追加轮次
- 自距离 / 跨端点距离 / Cross-Self Ratio 计算
- 相似度、可信度、可行度和最终结论输出
- 雷达图、热力图、原始响应和错误摘要展示
- 多种接口协议适配

### 需要特别说明的地方

虽然 `requirements.txt` 中包含了 `sentence-transformers`、`numpy`、`scipy` 等依赖，但当前仓库里真正落地的距离实现位于 `core/distance.py`，采用的是轻量启发式特征与 Markdown 结构特征，而不是已经接好的 Transformer 向量方案。

也就是说：README 这里描述的是当前代码已经实现的能力，不把设计稿或规划文档里的内容写成“已完成”。

## 审计方法概览

### 1. 主动探针

`core/probes.py` 当前定义了 8 个探针维度：

- metadata hallucination
- alignment boundary
- malformed syntax
- formatting quirks
- reasoning trap
- multilingual nuance
- coding style
- self identification

每个探针都不是单条问题，而是 3 轮对话：

1. 先建立上下文
2. 再缩小语境
3. 最后触发真正的识别型问题

这样做的目的，是更容易暴露目标接口在风格、推理、格式、身份、自我一致性等方面的底层差异。

### 2. 基线对照

`core/engine.py` 会在多轮采样中同时收集：

- 基线自身波动 `s_base`
- 目标自身波动 `s_target`
- 基线与目标之间的跨端点偏差 `c_cross`

系统随后对这些距离取中位数，并计算 Cross/Self Ratio，用于把“正常随机采样噪声”与“真实行为差异”区分开。

### 3. 输出指标

`core/statistics.py` 当前会输出几类核心指标：

- `ratio`：偏差比率
- `similarity`：目标与基线的相似度评分
- `confidence`：本次审计结果的可信度评分
- `verdict`：最终结论

结论目前包括：

- `VERIFIED`
- `FRAUD DETECTED`
- `INCONCLUSIVE`

### 4. 自适应采样

如果目标接口自身波动过大，系统会继续追加采样轮次，直到结果更稳定或者达到 12 轮上限。

## 支持的接口类型

`adapters/llm_gateway.py` 当前支持以下接口风格：

- `openai_responses`
- `openai_compatible`
- `anthropic_messages`
- `amazon_bedrock`
- `gemini_native`
- `gemini_openai_compatible`

当前实现包括：

- OpenAI 兼容接口的锁参数调用
- `/responses` 直接调用与解析
- `/chat/completions` 回退路径
- Anthropic 原生请求构造
- Gemini 原生请求构造
- Bedrock SigV4 签名路径
- 双语错误解释

## 界面功能

`app.py` 当前提供：

- 中英文界面切换
- 基线 / 目标双配置
- 接口类型相关参数输入
- 采样轮数控制
- 相似度、可信度、比率、可行度评分卡
- 8 维探针雷达图
- 跨轮次热力图
- 原始交互回看与状态筛选

图表在 `ui/charts.py`，主题样式在 `ui/theme.py`。

## 项目结构

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

## 安装

建议 Python 版本：`3.11+`

```bash
pip install -r requirements.txt
```

## 启动

```bash
streamlit run app.py
```

启动后在侧边栏配置：

- 基线 API Key 与模型
- 目标 API Key 与模型
- 双方 Base URL
- 接口格式
- 采样轮数
- 特定供应商运行参数

## 环境变量示例

仓库附带 `.env.example`：

```env
SHADOWHUNTER_BASELINE_API_KEY=replace-me
SHADOWHUNTER_TARGET_API_KEY=replace-me
SHADOWHUNTER_TARGET_BASE_URL=https://api.42w.shop/v1
SHADOWHUNTER_BASELINE_MODEL=gpt-5.2
SHADOWHUNTER_TARGET_MODEL=gpt-5.4-mini
```

## 测试

```bash
python -m pytest tests -q
```

当前测试覆盖：

- 默认表单状态与双语文案
- 多类供应商参数说明
- 结果结构与错误分类
- 自适应采样引擎行为
- 网关请求构造与回退逻辑
- Responses / OpenAI Compatible / Anthropic / Gemini / Bedrock 适配逻辑

## 如何理解结果

- 高 `similarity` + 高 `confidence`：目标行为接近基线，且本次审计较稳定
- 低 `similarity`：目标接口与基线存在明显行为偏差
- 低 `confidence`：虽然有结果，但目标接口不稳定、报错多或波动太大
- `INCONCLUSIVE`：系统认为当前证据不足，不给过强结论

这个工具适合作为审计辅助系统，而不是唯一证据来源。涉及采购、生产切换、合规判断时，建议结合原始响应、接口日志与人工复核共同判断。

## 当前限制

- 距离模型仍偏轻量和启发式
- 探针池目前是静态的，不是 RL 优化探针
- 当前是单进程应用，不是分布式审计平台
- 阈值逻辑透明，但未覆盖全部模型家族的精细校准
- 对非常强的代理转发层，后续仍需要更丰富的特征与更大的探针池
