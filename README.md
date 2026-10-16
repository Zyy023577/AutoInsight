# AutoInsight

汽车垂类智能问答与大模型策略优化系统。项目按阶段实现意图识别、汽车实体抽取、结构化知识检索、RAG 问答、Prompt 策略实验和模型评测。

## 当前状态：Phase 6

本阶段已实现：

- FastAPI 后端基础服务。
- SQLite 数据模型与本地初始化。
- 明确标记为 `demo` 的人工构造汽车数据。
- `/api/health`、`/api/cars`、`/api/cars/{car_id}` 基础 API。
- 预算、能源类型、车身类型、最低续航和使用场景的结构化过滤。
- Pydantic 响应校验与 pytest API 测试。
- 汽车领域七类意图标签与可解释规则 Baseline。
- 统一实体 Schema，支持车型别名、价格单位、续航、能源、车身、场景、配置和关注属性抽取。
- 区分硬约束、软偏好、否定约束，并保留规则命中的原文证据。
- `/api/nlp/analyze` 规则分析 API。
- OpenAI-compatible 结构化输出适配器；未配置密钥时不会调用外部服务。
- NetworkX 汽车知识图谱、来源元数据、车型关系查询和多车型对比。
- 硬约束优先的可解释推荐 API，支持软偏好权重调整和缺失数据说明。
- 基于 SQLite 结构化证据的 RAG 问答，支持无密钥 Demo 模式和显式 LLM 模式。
- 独立的 100 条汽车领域人工标注评测集，和 Few-shot 示例分离。
- 规则 Baseline 的意图、实体指标、混淆矩阵、延迟和错误案例报告。
- A/B/C 三组 Prompt 策略元数据、版本文件和真实调用评测执行器；无 API Key 时明确记录 `not_run_no_key`。
- React + TypeScript + Vite + Tailwind CSS 可视化策略工作台。
- 智能问答、知识图谱、模型评测、错误分析和 Prompt 实验五个前端页面。
- `/api/evaluation/report`、`/api/evaluation/errors` 和 `/api/evaluation/prompt` 评测接口。
- Swagger 文档：启动服务后访问 `http://127.0.0.1:8000/docs`。

Prompt 的 LLM 指标依赖外部 API Key，本地未配置密钥时不会产生真实模型结果；前端会显示规则 Baseline 和明确的不可用状态。

## Windows 启动

日常使用可以直接双击项目根目录的 [`start_autoinsight.cmd`](start_autoinsight.cmd)，它会分别打开后端、前端终端并启动浏览器。首次使用前仍需完成一次前端依赖安装：

```powershell
Set-Location H:\\CodexProjects\\AutoInsight\\frontend
npm.cmd install
```

之后双击启动脚本即可，不需要激活虚拟环境。

项目使用 Python 3.14.7。PowerShell 命令如下：

```powershell
python --version
python -m venv .venv314
.\.venv314\Scripts\python.exe -m pip install --upgrade pip
.\.venv314\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv314\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

如果确认显示 `Python 3.14.7`，也可以直接使用当前环境运行：

```powershell
python -m pip install -r backend\requirements.txt
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

另开一个 PowerShell 窗口启动前端：

```powershell
Set-Location H:\CodexProjects\AutoInsight\frontend
npm.cmd install
npm.cmd run dev
```

打开 `http://127.0.0.1:5173/`。Vite 会把 `/api` 请求代理到 `http://127.0.0.1:8000`。

### 前端配置模型 API

打开前端右上角的 `⚙ API 设置`，填写：

- API Key
- Base URL，默认 `https://api.deepseek.com`
- Model，默认 `deepseek-chat`

勾选“记住配置到本机 `.env`”后，配置会保存到本机根目录 `.env`，后端重启后自动加载；该文件已加入 `.gitignore`，不会提交到 Git。未勾选时只保存到当前后端进程内存，适合临时测试。API Key 不会返回到前端页面。

## 测试

```powershell
python -m pytest backend\tests -q
```

运行 Phase 5 评测：

```powershell
python scripts\run_evaluation.py
```

报告输出到 `reports/generated/`：`evaluation_report.md`、`evaluation_results.json`、`rule_baseline_records.csv` 和 `error_cases.json`。配置 `DEEPSEEK_API_KEY` 或 `OPENAI_API_KEY` 后，脚本才会对同一评测集逐条运行 A/B/C，并额外生成 `prompt_strategy_records.csv`；未配置密钥时三组策略保持 `not_run_no_key`。

首次启动会创建 `data/autoinsight.db`。该文件是本地运行产物，已加入 `.gitignore`。Demo 数据来源和限制见 [`data/demo/README.md`](data/demo/README.md)。

## API 示例

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod 'http://127.0.0.1:8000/api/cars?price_max=200000&energy_type=纯电&body_type=SUV&range_min_km=500'
Invoke-RestMethod http://127.0.0.1:8000/api/nlp/analyze -Method Post -ContentType 'application/json' -Body '{"text":"我想买一辆20万以内、续航500公里以上、适合家用的纯电SUV。"}'
Invoke-RestMethod http://127.0.0.1:8000/api/recommendations -Method Post -ContentType 'application/json' -Body '{"budget_max":200000,"energy_type":"纯电","body_type":"SUV","range_min_km":500,"usage_scenario":"家庭使用","preferred_attributes":["续航"]}'
Invoke-RestMethod http://127.0.0.1:8000/api/qa/answer -Method Post -ContentType 'application/json' -Body '{"question":"20万以内有什么纯电SUV推荐？"}'
```
