import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "./api";
import type {
  CarRecord,
  ErrorCase,
  EvaluationReport,
  GraphNode,
  KnowledgeGraphResponse,
  NlpAnalysis,
  PromptExperimentResponse,
  RagAnswerResponse,
  ViewKey,
} from "./types";

const navItems: Array<{ key: ViewKey; label: string; hint: string; icon: string }> = [
  { key: "qa", label: "智能问答", hint: "RAG evidence", icon: "◈" },
  { key: "graph", label: "知识图谱", hint: "Entity graph", icon: "⌘" },
  { key: "evaluation", label: "模型评测", hint: "Metrics lab", icon: "▦" },
  { key: "errors", label: "错误分析", hint: "Error cases", icon: "△" },
  { key: "prompt", label: "Prompt 实验", hint: "Strategy test", icon: "✦" },
];

const strategyNames: Record<string, string> = {
  A: "基础 Prompt",
  B: "结构化 Prompt",
  C: "Few-shot Prompt",
};

function formatValue(value: unknown): string {
  if (Array.isArray(value)) return value.join("、");
  if (value && typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value ?? "—");
}

function formatMoney(value?: number | null): string {
  return value == null ? "暂无" : `${(value / 10000).toFixed(1)} 万`;
}

function Badge({ children, tone = "cyan" }: { children: ReactNode; tone?: "cyan" | "lime" | "muted" | "red" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`panel ${className}`}>{children}</section>;
}

function SectionHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return (
    <div className="section-heading">
      <p className="eyebrow">{eyebrow}</p>
      <h2>{title}</h2>
      <p className="muted">{description}</p>
    </div>
  );
}

function StatCard({ label, value, detail, accent = "cyan" }: { label: string; value: string; detail: string; accent?: "cyan" | "lime" }) {
  return (
    <div className={`stat-card stat-${accent}`}>
      <p className="muted text-xs uppercase tracking-[0.16em]">{label}</p>
      <strong>{value}</strong>
      <span>{detail}</span>
    </div>
  );
}

function App() {
  const [view, setView] = useState<ViewKey>("qa");
  const [health, setHealth] = useState<{ carCount: number; status: string } | null>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    api.health()
      .then((result) => setHealth({ carCount: result.car_count, status: result.status }))
      .catch((error: Error) => setGlobalError(error.message));
  }, []);

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="rail-mark">AI</div>
        <nav className="nav-stack" aria-label="主导航">
          {navItems.map((item) => (
            <button key={item.key} title={item.label} aria-label={item.label} className={`nav-item ${view === item.key ? "active" : ""}`} onClick={() => setView(item.key)}>
              <span className="nav-icon">{item.icon}</span>
              {view === item.key && <span className="nav-pulse" />}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button className="rail-settings" title="API 设置" aria-label="API 设置" onClick={() => setSettingsOpen(true)}>⚙</button>
        </div>
      </aside>

      <main className="main-stage">
        <header className="topbar">
          <div className="topbar-brand"><div className="brand-mark">AI</div><div><div className="brand-name">AutoInsight AI</div><div className="brand-caption">STRATEGY ANALYTICS</div></div></div>
          <nav className="top-nav" aria-label="工作台导航">
            {navItems.map((item) => <button key={item.key} className={view === item.key ? "active" : ""} onClick={() => setView(item.key)}>{item.label}</button>)}
          </nav>
          <div className="topbar-right"><Badge tone="lime">{health?.status === "ok" ? "ONLINE" : "CHECKING"}</Badge><button className="settings-button" onClick={() => setSettingsOpen(true)} aria-label="打开 API 设置">设置</button></div>
        </header>
        {globalError && <div className="global-error">请求或模型输出处理失败：{globalError}。如果是连接错误，请确认 FastAPI 已运行在 127.0.0.1:8000。</div>}
        <div className="content-wrap">
          {view === "qa" && <QaView onError={setGlobalError} health={health} />}
          {view === "graph" && <GraphView onError={setGlobalError} />}
          {view === "evaluation" && <EvaluationView onError={setGlobalError} />}
          {view === "errors" && <ErrorsView onError={setGlobalError} />}
          {view === "prompt" && <PromptView onError={setGlobalError} />}
        </div>
        {settingsOpen && <SettingsModal onClose={() => setSettingsOpen(false)} onError={setGlobalError} />}
      </main>
    </div>
  );
}

function SettingsModal({ onClose, onError }: { onClose: () => void; onError: (message: string | null) => void }) {
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("https://api.deepseek.com");
  const [model, setModel] = useState("deepseek-chat");
  const [persist, setPersist] = useState(false);
  const [configured, setConfigured] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.llmSettings().then((result) => {
      setConfigured(result.configured);
      setBaseUrl(result.base_url);
      setModel(result.model);
      setPersist(result.persistence === "local_env");
    }).catch((error: Error) => onError(error.message));
  }, [onError]);

  async function save() {
    setSaving(true);
    setMessage("");
    onError(null);
    try {
      const result = await api.configureLLM({ api_key: apiKey, base_url: baseUrl, model, persist });
      setConfigured(result.configured);
      setApiKey("");
      setMessage(result.persistence === "local_env" ? "已保存到本机 .env，重启后自动生效" : "API Key 已配置到当前后端进程");
    } catch (error) {
      setMessage((error as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}><div className="settings-modal" role="dialog" aria-modal="true" aria-label="API 设置"><div className="panel-title-row"><div><p className="eyebrow">LOCAL MODEL SETTINGS</p><h3>配置模型 API</h3></div><button className="close-button" onClick={onClose} aria-label="关闭">×</button></div><p className="settings-description">Key 只发送到本机后端。勾选持久化后会保存到本机 .env，文件不会提交到 Git。</p><div className="settings-status"><span className={`status-dot ${configured ? "online" : ""}`} />{configured ? "已配置模型 Key" : "尚未配置模型 Key"}</div><label className="settings-field"><span>API Key</span><input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={configured ? "已配置，留空可保留当前 Key" : "sk-..."} autoComplete="off" /></label><label className="settings-field"><span>Base URL</span><input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} /></label><label className="settings-field"><span>Model</span><input value={model} onChange={(event) => setModel(event.target.value)} /></label><label className="settings-checkbox"><input type="checkbox" checked={persist} onChange={(event) => setPersist(event.target.checked)} /><span>记住配置到本机 .env（推荐本地开发使用）</span></label>{message && <div className="settings-message">{message}</div>}<div className="settings-actions"><button className="secondary-button" onClick={onClose}>取消</button><button className="primary-button" onClick={save} disabled={saving}>{saving ? "SAVING..." : "SAVE CONFIG  ↗"}</button></div></div></div>;
}

function QaView({ onError, health }: { onError: (message: string | null) => void; health: { carCount: number; status: string } | null }) {
  const [question, setQuestion] = useState("20万以内有什么纯电SUV推荐？");
  const [mode, setMode] = useState("demo_grounded");
  const [result, setResult] = useState<RagAnswerResponse | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    onError(null);
    try {
      setResult(await api.ask(question, mode));
    } catch (error) {
      onError((error as Error).message);
    } finally {
      setLoading(false);
    }
  }

  const entityEntries = result ? Object.entries(result.analysis.entities).filter(([, value]) => value != null && (!Array.isArray(value) || value.length > 0)) : [];

  return (
    <>
      <div className="overview-heading"><div><p className="eyebrow">OVERVIEW / GROUNDED QA</p><h1>汽车策略分析工作台</h1><p className="muted">从用户问题到可验证回答，观察 AutoInsight 的完整推理链路。</p></div><div className="overview-meta"><span className={`status-dot ${health?.status === "ok" ? "online" : ""}`} />{health?.status === "ok" ? "本地 API 已连接" : "正在连接本地 API"}<small>最后同步 · 本地运行</small></div></div>
      <div className="dashboard-stat-grid"><div className="dashboard-stat stat-blue"><div className="stat-icon">⌂</div><div><span>汽车实体</span><strong>{health?.carCount ?? "—"}</strong><small>结构化车型记录</small></div></div><div className="dashboard-stat stat-sage"><div className="stat-icon">◌</div><div><span>知识检索</span><strong>SQLite</strong><small>可追溯证据链</small></div></div><div className="dashboard-stat stat-sand"><div className="stat-icon">✦</div><div><span>问答模式</span><strong>RAG</strong><small>Grounded answer</small></div></div><div className="dashboard-stat stat-cream"><div className="stat-icon">↗</div><div><span>实验状态</span><strong>Live</strong><small>A / B / C 可切换</small></div></div></div>
      <div className="workspace-section-title"><div><p className="eyebrow">WORKSPACE</p><h2>开始一次可验证分析</h2></div><span className="section-note">Intent → Entity → Retrieval → Answer</span></div>
      <Panel className="query-panel">
        <div className="query-meta"><Badge>RAG PIPELINE</Badge><span>Intent → Entity → Retrieval → Answer</span></div>
        <textarea value={question} onChange={(event) => setQuestion(event.target.value)} className="question-input" rows={3} placeholder="输入汽车购车问题..." />
        <div className="query-actions">
          <label className="select-wrap"><span>Answer mode</span><select value={mode} onChange={(event) => setMode(event.target.value)}><option value="demo_grounded">Demo grounded</option><option value="llm_grounded">LLM grounded</option></select></label>
          <button className="primary-button" onClick={submit} disabled={loading || !question.trim()}>{loading ? "ANALYZING..." : "RUN ANALYSIS  ↗"}</button>
        </div>
      </Panel>
      <div className="pipeline-strip"><div><span>01</span><strong>理解意图</strong><small>识别购车、对比或参数查询</small></div><i>→</i><div><span>02</span><strong>抽取实体</strong><small>预算、能源、车型和场景</small></div><i>→</i><div><span>03</span><strong>检索证据</strong><small>优先使用结构化 Demo 数据</small></div><i>→</i><div><span>04</span><strong>生成回答</strong><small>展示来源与可验证依据</small></div></div>
      {!result && <div className="empty-state"><span className="empty-icon">◌</span><h3>等待一次真实 API 调用</h3><p>后端默认使用结构化 Demo 数据，回答会附带证据来源。</p></div>}
      {result && (
        <div className="qa-grid">
          <Panel className="analysis-card">
            <div className="panel-title-row"><div><p className="eyebrow">ANALYSIS</p><h3>意图识别与实体抽取</h3></div><Badge tone={result.grounded ? "lime" : "red"}>{result.grounded ? "GROUNDED" : "REFUSED"}</Badge></div>
            <div className="intent-display"><span>主意图</span><strong>{result.analysis.intent}</strong><small>{result.analysis.strategy}</small></div>
            <div className="entity-grid">{entityEntries.length ? entityEntries.map(([key, value]) => <div className="entity-item" key={key}><span>{key}</span><strong>{formatValue(value)}</strong></div>) : <p className="muted">未抽取到显式实体</p>}</div>
          </Panel>
          <Panel className="answer-card">
            <div className="panel-title-row"><div><p className="eyebrow">GROUNDED ANSWER</p><h3>回答与依据</h3></div><span className="citation-count">{result.citations.length} citations</span></div>
            <div className="answer-copy">{result.answer}</div>
            {result.refusal_reason && <div className="warning-box">{result.refusal_reason}</div>}
            <div className="evidence-list">{result.evidence.map((item) => <div className="evidence-item" key={item.evidence_id}><div className="evidence-id">{item.evidence_id}</div><div><strong>{item.statement}</strong><small>{item.provenance.source_name} · {item.provenance.collected_at} · {item.provenance.data_status}</small></div></div>)}</div>
          </Panel>
        </div>
      )}
    </>
  );
}

function GraphView({ onError }: { onError: (message: string | null) => void }) {
  const [cars, setCars] = useState<CarRecord[]>([]);
  const [selectedCar, setSelectedCar] = useState("");
  const [graph, setGraph] = useState<KnowledgeGraphResponse | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  useEffect(() => {
    Promise.all([api.cars(), api.graph()]).then(([carResult, graphResult]) => { setCars(carResult.cars); setGraph(graphResult); }).catch((error: Error) => onError(error.message));
  }, [onError]);

  useEffect(() => {
    if (!selectedCar) return;
    api.graph(selectedCar).then(setGraph).catch((error: Error) => onError(error.message));
  }, [selectedCar, onError]);

  const positions = useMemo(() => {
    if (!graph) return new Map<string, { x: number; y: number }>();
    const map = new Map<string, { x: number; y: number }>();
    graph.nodes.forEach((node, index) => map.set(node.id, { x: 72 + (index % 6) * 138, y: 58 + Math.floor(index / 6) * 58 }));
    return map;
  }, [graph]);

  return (
    <>
      <SectionHeading eyebrow="02 / KNOWLEDGE GRAPH" title="从车型实体走向可追溯关系" description="NetworkX 构建的轻量级汽车知识结构，节点和边均来自后端结构化数据。" />
      <div className="toolbar-row"><label className="select-wrap"><span>聚焦车型</span><select value={selectedCar} onChange={(event) => setSelectedCar(event.target.value)}><option value="">全部车型</option>{cars.map((car) => <option key={car.id} value={car.id}>{car.brand} {car.model}</option>)}</select></label><Badge tone="lime">{graph?.nodes.length ?? 0} nodes · {graph?.edges.length ?? 0} edges</Badge></div>
      <div className="graph-layout">
        <Panel className="graph-panel"><div className="graph-legend"><span><i className="legend-dot brand-dot" />品牌</span><span><i className="legend-dot model-dot" />车型</span><span><i className="legend-dot attribute-dot" />版本 / 属性 / 观点</span></div><svg viewBox="0 0 840 700" className="graph-canvas" role="img" aria-label="汽车知识图谱">{graph?.edges.map((edge) => { const source = positions.get(edge.source); const target = positions.get(edge.target); return source && target ? <g key={`${edge.source}-${edge.target}-${edge.relation}`}><line x1={source.x} y1={source.y} x2={target.x} y2={target.y} className="graph-edge" /><text x={(source.x + target.x) / 2} y={(source.y + target.y) / 2 - 6} className="edge-label">{edge.relation}</text></g> : null; })}{graph?.nodes.map((node) => { const position = positions.get(node.id); const nodeTone = node.node_type === "brand" ? "brand" : node.node_type === "model" ? "model" : "attribute"; return position ? <g key={node.id} className="graph-node" onClick={() => setSelectedNode(node)}><circle cx={position.x} cy={position.y} r={node.node_type === "model" ? 25 : 20} className={`node-circle ${nodeTone}`} /><text x={position.x} y={position.y + 4} textAnchor="middle" className="node-label">{node.label.length > 12 ? `${node.label.slice(0, 12)}…` : node.label}</text></g> : null; })}</svg></Panel>
        <Panel className="detail-panel"><p className="eyebrow">NODE INSPECTOR</p>{selectedNode ? <><h3>{selectedNode.label}</h3><Badge>{selectedNode.node_type}</Badge><div className="property-list">{Object.entries(selectedNode.properties).map(([key, value]) => <div key={key}><span>{key}</span><strong>{formatValue(value)}</strong></div>)}</div></> : <div className="inspector-empty"><span>⌁</span><p>点击图谱节点查看实体属性和来源信息。</p></div>}</Panel>
      </div>
    </>
  );
}

function EvaluationView({ onError }: { onError: (message: string | null) => void }) {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  useEffect(() => { api.evaluation().then(setReport).catch((error: Error) => onError(error.message)); }, [onError]);
  const baseline = report?.rule_baseline;
  const chartData = report ? [{ name: "Baseline", accuracy: (baseline?.accuracy ?? 0) * 100, macroF1: (baseline?.macro_f1 ?? 0) * 100 }, ...report.prompt_strategies.filter((item) => item.metrics).map((item) => ({ name: item.strategy_id, accuracy: (item.metrics?.accuracy ?? 0) * 100, macroF1: (item.metrics?.macro_f1 ?? 0) * 100 }))] : [];
  return (
    <>
      <SectionHeading eyebrow="03 / EVALUATION LAB" title="让策略差异落在真实实验结果上" description="指标来自 reports/generated/evaluation_results.json，不在前端写入模拟成绩。" />
      {baseline && <><div className="stat-grid"><StatCard label="Accuracy" value={`${((baseline.accuracy ?? 0) * 100).toFixed(1)}%`} detail="100 条测试样本" /><StatCard label="Macro-F1" value={`${((baseline.macro_f1 ?? 0) * 100).toFixed(1)}%`} detail="七类意图平均" accent="lime" /><StatCard label="Entity F1" value={`${((baseline.entity?.f1 ?? 0) * 100).toFixed(1)}%`} detail="字段级 mention 评测" /><StatCard label="P95 latency" value={`${baseline.latency_ms.p95 ?? "—"} ms`} detail="当前本地运行" accent="lime" /></div><div className="evaluation-grid"><Panel><div className="panel-title-row"><div><p className="eyebrow">STRATEGY COMPARISON</p><h3>识别效果对比</h3></div><Badge>{report?.dataset_type}</Badge></div><div className="chart-wrap"><ResponsiveContainer width="100%" height="100%"><BarChart data={chartData}><CartesianGrid strokeDasharray="3 3" stroke="#e5e5df" vertical={false} /><XAxis dataKey="name" stroke="#899395" tickLine={false} axisLine={false} /><YAxis domain={[0, 100]} stroke="#899395" tickLine={false} axisLine={false} tickFormatter={(value) => `${value}%`} /><Tooltip contentStyle={{ background: "#ffffff", border: "1px solid #deded8", borderRadius: 10, color: "#344148" }} formatter={(value: number) => `${value.toFixed(1)}%`} /><Bar dataKey="accuracy" name="Accuracy" fill="#829aaa" radius={[5, 5, 0, 0]} /><Bar dataKey="macroF1" name="Macro-F1" fill="#9db49e" radius={[5, 5, 0, 0]} /></BarChart></ResponsiveContainer></div></Panel><Panel><div className="panel-title-row"><div><p className="eyebrow">PER INTENT</p><h3>类别表现</h3></div><span className="muted">Accuracy</span></div><div className="intent-table">{Object.entries(baseline.per_intent_accuracy ?? {}).map(([intent, score]) => <div key={intent}><span>{intent}</span><div className="progress-track"><i style={{ width: `${score * 100}%` }} /></div><strong>{(score * 100).toFixed(1)}%</strong></div>)}</div></Panel></div><Panel className="strategy-table-panel"><div className="panel-title-row"><div><p className="eyebrow">PROMPT STATUS</p><h3>A / B / C 策略状态</h3></div><span className="muted">同一评测集</span></div><table><thead><tr><th>策略</th><th>版本</th><th>状态</th><th>Accuracy</th><th>Macro-F1</th></tr></thead><tbody>{report.prompt_strategies.map((item) => <tr key={item.strategy_id}><td><strong>{item.strategy_id} · {item.name}</strong></td><td className="mono">{item.version}</td><td><Badge tone={item.status === "completed" ? "lime" : "muted"}>{item.status}</Badge></td><td>{item.metrics?.accuracy ?? "—"}</td><td>{item.metrics?.macro_f1 ?? "—"}</td></tr>)}</tbody></table></Panel></>}
    </>
  );
}

function ErrorsView({ onError }: { onError: (message: string | null) => void }) {
  const [errors, setErrors] = useState<ErrorCase[]>([]);
  const [filter, setFilter] = useState("all");
  useEffect(() => { api.errors().then(setErrors).catch((error: Error) => onError(error.message)); }, [onError]);
  const filtered = filter === "all" ? errors : errors.filter((item) => item.strategy_id === filter);
  return (
    <>
      <SectionHeading eyebrow="04 / ERROR ANALYSIS" title="错误不是黑盒里的数字" description="查看误判样本、预期标签和实际输出，为下一轮规则或 Prompt 调整提供依据。" />
      <div className="toolbar-row"><div className="filter-tabs">{["all", "rule", "A", "B", "C"].map((key) => <button key={key} className={filter === key ? "selected" : ""} onClick={() => setFilter(key)}>{key === "all" ? "全部" : key}</button>)}</div><Badge tone="red">{filtered.length} cases</Badge></div>
      <Panel className="error-table-panel"><table><thead><tr><th>来源</th><th>样本</th><th>用户问题</th><th>预期</th><th>实际</th><th>错误类型</th></tr></thead><tbody>{filtered.map((item) => <tr key={`${item.strategy_id}-${item.sample_id}`}><td><Badge tone={item.strategy_id === "rule" ? "muted" : "cyan"}>{item.strategy_id}</Badge></td><td className="mono">{item.sample_id}</td><td className="question-cell">{item.text}</td><td>{item.expected_intent}</td><td className={item.predicted_intent ? "" : "text-red-300"}>{item.predicted_intent ?? "解析失败"}</td><td><span className="error-type">{item.error_type}</span></td></tr>)}</tbody></table>{filtered.length === 0 && <div className="empty-table">暂无错误案例</div>}</Panel>
    </>
  );
}

function PromptView({ onError }: { onError: (message: string | null) => void }) {
  const [text, setText] = useState("小米SU7和特斯拉Model Y谁的续航更好？");
  const [strategy, setStrategy] = useState<"A" | "B" | "C">("B");
  const [baseline, setBaseline] = useState<NlpAnalysis | null>(null);
  const [result, setResult] = useState<PromptExperimentResponse | null>(null);
  const [loading, setLoading] = useState(false);
  async function run() {
    setLoading(true);
    onError(null);
    try {
      const baselineResult = await api.analyze(text);
      setBaseline(baselineResult);
      setResult(await api.prompt(text, strategy));
    } catch (error) {
      onError((error as Error).message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  }
  return (
    <>
      <SectionHeading eyebrow="05 / PROMPT EXPERIMENT" title="在同一个问题上观察策略差异" description="单题实验调用真实后端；未配置 API Key 时保留规则 Baseline，并明确提示 LLM 策略不可用。" />
      <Panel className="prompt-input-panel"><div className="strategy-tabs">{(["A", "B", "C"] as const).map((item) => <button key={item} className={strategy === item ? "selected" : ""} onClick={() => setStrategy(item)}><b>{item}</b><span>{strategyNames[item]}</span></button>)}</div><textarea value={text} onChange={(event) => setText(event.target.value)} className="question-input" rows={3} /><button className="primary-button" onClick={run} disabled={loading || !text.trim()}>{loading ? "RUNNING STRATEGY..." : `RUN ${strategy} EXPERIMENT  ↗`}</button></Panel>
      <div className="experiment-grid"><Panel><p className="eyebrow">RULE BASELINE</p><h3>可用的离线基线</h3>{baseline ? <ResultBlock intent={baseline.intent} entities={baseline.entities} meta={baseline.strategy} /> : <p className="muted">运行实验后显示基线输出。</p>}</Panel><Panel><div className="panel-title-row"><div><p className="eyebrow">SELECTED STRATEGY</p><h3>{strategy} · {strategyNames[strategy]}</h3></div>{result && <Badge tone="lime">LIVE OUTPUT</Badge>}</div>{result ? <><ResultBlock intent={result.intent} entities={result.entities} meta={`${result.prompt_version} · ${result.latency_ms ?? "—"} ms`} /><details className="raw-output"><summary>查看原始 JSON 输出</summary><pre>{result.raw_output}</pre></details></> : <div className="locked-state"><span>⊘</span><strong>等待真实模型响应</strong><small>需要配置 DEEPSEEK_API_KEY 或 OPENAI_API_KEY</small></div>}</Panel></div>
    </>
  );
}

function ResultBlock({ intent, entities, meta }: { intent: string; entities: NlpAnalysis["entities"] | Record<string, unknown>; meta: string }) {
  return <div className="result-block"><div className="result-intent"><span>intent</span><strong>{intent}</strong><small>{meta}</small></div><div className="result-entities">{Object.entries(entities).filter(([, value]) => value != null && (!Array.isArray(value) || value.length > 0)).map(([key, value]) => <div key={key}><span>{key}</span><strong>{formatValue(value)}</strong></div>)}</div></div>;
}

export default App;
