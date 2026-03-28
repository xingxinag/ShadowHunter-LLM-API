# ShadowHunter-X Streamlit Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重建 ShadowHunter-X 为严格符合新开发文档的 Streamlit 单体应用，包含 LiteLLM 统一网关、8 维探针与三轮陷阱、多模态距离、Cross/Self Ratio 评分、以及单进程仪表盘 UI。

**Architecture:** 应用以 `app.py` 为唯一入口，UI、调度、算法、适配器全部运行在同一个 Python 进程内。`core/` 负责探针、距离、统计和异步调度，`adapters/` 负责统一 LLM 网关，`ui/` 负责 Streamlit 主题与 ECharts option 生成；所有阻塞型外部调用由异步引擎集中管理。

**Tech Stack:** Python 3.11, Streamlit, streamlit-echarts, LiteLLM, sentence-transformers, numpy, scipy, tenacity, pytest.

---

### Task 1: 建立单体项目骨架与配置合同

**Files:**
- Create: `app.py`
- Create: `core/__init__.py`
- Create: `core/probes.py`
- Create: `ui/__init__.py`
- Create: `ui/theme.py`
- Create: `ui/charts.py`
- Create: `adapters/__init__.py`
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `README.md`
- Test: `tests/test_probes.py`

**Step 1: Write the failing test**

覆盖：
- 8 个探针维度完整存在
- 每个探针可生成 3 轮陷阱对话
- UI 图表输入合同包含雷达图和热力图所需字段

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_probes.py -q`
Expected: FAIL，因为探针与图表合同尚未实现。

**Step 3: Write minimal implementation**

创建单体项目骨架、8 维探针定义、三轮陷阱生成器、图表 option 生成器和基础说明文件。

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_probes.py -q`
Expected: PASS.

### Task 2: 完成 LiteLLM 统一网关

**Files:**
- Create: `adapters/llm_gateway.py`
- Test: `tests/test_gateway.py`

**Step 1: Write the failing test**

覆盖：
- `openai-compatible` 不加前缀
- 其他 provider 使用 `provider/model`
- 采样参数固定为 `temperature=0.3`、`top_p=0.9`、`max_tokens=512`、`seed=4242`
- 非限流错误返回 `[ERROR] ...`

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_gateway.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

实现 `UnifiedGateway`、模型路由格式化和重试兼容的异步生成接口。

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_gateway.py -q`
Expected: PASS.

### Task 3: 完成多模态距离计算

**Files:**
- Create: `core/distance.py`
- Test: `tests/test_distance.py`

**Step 1: Write the failing test**

覆盖：
- 语义余弦距离相同文本为 0
- Markdown 标签提取可识别标题、列表、代码块
- 综合距离按 `0.8 * semantic + 0.2 * structural` 加权

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_distance.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

实现嵌入编码抽象、结构标签提取、Jaccard 结构距离和综合距离函数。

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_distance.py -q`
Expected: PASS.

### Task 4: 完成统计算法与自适应采样判定

**Files:**
- Create: `core/statistics.py`
- Test: `tests/test_statistics.py`

**Step 1: Write the failing test**

覆盖：
- `S_base`、`S_target`、`C_cross` 使用中位数
- Similarity 使用新公式 `exp(-1.5 * max(0, ratio - 1.1))`
- Confidence 使用成功率和 `S_target / 0.5` 惩罚
- 当 `S_target` 过大时触发追加采样建议，且最大轮数为 12

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_statistics.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

实现比率、相似度、可信度、结论以及自适应轮次建议逻辑。

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_statistics.py -q`
Expected: PASS.

### Task 5: 完成审计引擎

**Files:**
- Create: `core/engine.py`
- Test: `tests/test_engine.py`

**Step 1: Write the failing test**

覆盖：
- 引擎会按 8 维探针并发执行 baseline/target
- 每个维度是 3 轮对话陷阱，最终保留原始交互
- 高方差时会追加轮次但不超过 12
- 进度回调会收到轮次进度

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_engine.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

实现异步审计引擎、任务矩阵、结果聚合和进度回调。

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_engine.py -q`
Expected: PASS.

### Task 6: 完成 Streamlit 页面入口

**Files:**
- Modify: `app.py`
- Test: `tests/test_app.py`

**Step 1: Write the failing test**

覆盖：
- 页面配置、默认侧边栏字段和轮次范围符合文档
- 渲染结果区时包含 similarity、confidence、ratio、raw interactions

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_app.py -q`
Expected: FAIL.

**Step 3: Write minimal implementation**

实现 Streamlit 页面骨架、结果渲染辅助函数和 Expander 原始数据区。

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_app.py -q`
Expected: PASS.

### Task 7: 完成整体验证与运行说明

**Files:**
- Modify: `README.md`
- Modify: `requirements.txt`
- Modify: `.env.example`

**Step 1: Write the failing test**

补充对 README 关键命令和依赖文件的断言，确保文档反映 Streamlit 单体运行方式。

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_app.py tests/test_probes.py -q`
Expected: FAIL if docs/run instructions are inconsistent.

**Step 3: Write minimal implementation**

更新运行命令为 `streamlit run app.py`，并补齐依赖和环境变量模板。

**Step 4: Run test to verify it passes**

Run: `pytest tests -q`
Expected: PASS.
