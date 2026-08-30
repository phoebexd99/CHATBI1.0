"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import MetricChart from "./MetricChart";

type Evidence = {
  id: string; type: string; title: string; text?: string; score: number;
  keyword_score: number; vector_score: number; match_reason?: string;
};
type TraceItem = { node: string; status: "ok" | "skipped" | "error"; duration_ms: number; detail?: string };
type Result = {
  question: string; intent?: string; answer: string; sql: string; columns: string[]; rows: unknown[][];
  chart: { type: string; x?: string | null; y?: string };
  evidence: Evidence[]; trace: TraceItem[]; latency_ms: number;
  insight?: { title?: string; summary?: string; highlights?: string[] };
  retrieval_summary?: { hits?: number; top_score?: number; certified_hits?: number; target_hit?: boolean };
  entities?: { metric?: string; dimensions?: string[]; time_range?: string; filters?: Record<string, string | string[]> };
};
type StreamEvent =
  | { type: "trace"; trace: TraceItem; node: string }
  | { type: "result"; result: Result }
  | { type: "error"; error: { category: string; message: string }; trace: TraceItem[] };
type Dataset = {
  id: string; name: string; source_type: "template" | "excel" | "csv"; description: string;
  row_count: number; table_count: number; suggestions: string[];
};

const liveSuggestions = [
  "最近 30 天 GMV 是多少？",
  "最近 30 天各品类 GMV",
  "哪个线索来源的成交转化率最高？",
  "不同卖家的平均配送时长",
  "低评分订单主要集中在哪些品类？",
  "GMV 的定义是什么？",
];
const replaySuggestions = ["最近 30 天 GMV 是多少？"];
const phases = [
  ["interpret", "理解问题"], ["prepare", "确认口径"], ["analyze", "分析数据"], ["insight", "生成结论"],
];

function phaseForTrace(node: string): number {
  if (["classify", "extract_entities", "check_ambiguity"].includes(node)) return 0;
  if (["retrieve", "semantic_plan", "generate_sql"].includes(node)) return 1;
  if (["safety", "dry_run", "repair_once", "execute"].includes(node)) return 2;
  return 3;
}

function TraceList({ trace, expanded, onExpand }: { trace: TraceItem[]; expanded: string | null; onExpand: (node: string) => void }) {
  return <div className="trace-list">{trace.map((item, index) => <button className={`trace-item trace-${item.status}`} key={`${item.node}-${index}`} onClick={() => onExpand(item.node)}><span className="trace-index">{item.status === "error" ? "!" : item.status === "skipped" ? "–" : index + 1}</span><span className="trace-node"><strong>{item.node}</strong>{expanded === item.node && <small>{item.detail ?? (item.status === "ok" ? "节点完成，结果已写入共享状态" : `节点状态：${item.status}`)}</small>}</span><span className="trace-ms">{item.status} · {item.duration_ms} ms</span></button>)}</div>;
}

export default function QueryWorkspace() {
  const [question, setQuestion] = useState(liveSuggestions[0]);
  const [result, setResult] = useState<Result | null>(null);
  const [streamTrace, setStreamTrace] = useState<TraceItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [errorCategory, setErrorCategory] = useState("");
  const [status, setStatus] = useState<"idle" | "running" | "success" | "error">("idle");
  const [activePhase, setActivePhase] = useState(-1);
  const [showTechnical, setShowTechnical] = useState(false);
  const [expandedEvidence, setExpandedEvidence] = useState<string | null>(null);
  const [expandedTrace, setExpandedTrace] = useState<string | null>(null);
  const replay = process.env.NEXT_PUBLIC_DEMO_MODE === "replay";
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetId, setDatasetId] = useState("demo");
  const [datasetLoading, setDatasetLoading] = useState(!replay);
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
  const selectedDataset = datasets.find(item => item.id === datasetId);
  const suggestions = replay ? replaySuggestions : selectedDataset?.suggestions?.length ? selectedDataset.suggestions : liveSuggestions;
  const displayTrace = result?.trace ?? streamTrace;
  const visibleHighlights = (result?.insight?.highlights ?? []).filter(item => !/(SQL|dry[- ]run|安全门|allow[- ]list|RAG|Trace|节点)/i.test(item));

  const completedPhases = useMemo<Set<number>>(() => new Set<number>(displayTrace.filter(item => item.status !== "error").map(item => phaseForTrace(item.node))), [displayTrace]);

  useEffect(() => {
    const requestedDataset = new URLSearchParams(window.location.search).get("dataset");
    if (replay) {
      setDatasets([{ id: "demo", name: "电商经营演示模板", source_type: "template", description: "内置公开电商演示数据，可直接体验完整问数链路。", row_count: 120, table_count: 6, suggestions: replaySuggestions }]);
      setDatasetLoading(false);
      return;
    }
    fetch(`${apiBase}/api/datasets`)
      .then(response => response.ok ? response.json() : Promise.reject(new Error(`数据集请求失败 (${response.status})`)))
      .then((payload: { items: Dataset[] }) => {
        setDatasets(payload.items);
        const requested = payload.items.find(item => item.id === requestedDataset);
        if (requested) {
          setDatasetId(requested.id);
          if (requested.suggestions?.[0]) setQuestion(requested.suggestions[0]);
        }
      })
      .catch(() => setError("暂时无法读取数据源列表，请确认 Live API 已启动。"))
      .finally(() => setDatasetLoading(false));
  }, [apiBase, replay]);

  function changeDataset(nextId: string) {
    setDatasetId(nextId);
    const next = datasets.find(item => item.id === nextId);
    if (next?.suggestions?.[0]) setQuestion(next.suggestions[0]);
    setResult(null); setStreamTrace([]); setStatus("idle"); setError(""); setErrorCategory("");
  }

  async function ask(nextQuestion = question) {
    const trimmed = nextQuestion.trim();
    if (!trimmed) { setError("先输入一个经营问题。"); return; }
    setLoading(true); setStatus("running"); setError(""); setErrorCategory(""); setQuestion(trimmed);
    setResult(null); setStreamTrace([]); setActivePhase(0); setShowTechnical(false); setExpandedEvidence(null); setExpandedTrace(null);
    try {
      if (replay) {
        const response = await fetch(`${basePath}/replay/recent-30d-gmv.json`);
        if (!response.ok) throw new Error(`Replay fixture 请求失败 (${response.status})`);
        const next = await response.json() as Result;
        setStreamTrace(next.trace); setResult(next); setStatus("success"); setActivePhase(4);
        return;
      }
      const response = await fetch(`${apiBase}/api/query/stream`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: trimmed, dataset_id: datasetId }),
      });
      if (!response.ok || !response.body) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail?.message ?? `请求失败 (${response.status})`);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let terminal = false;
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const blocks = buffer.split("\n\n");
        buffer = blocks.pop() ?? "";
        for (const block of blocks) {
          const data = block.split("\n").find(line => line.startsWith("data: "))?.slice(6);
          if (!data) continue;
          const event = JSON.parse(data) as StreamEvent;
          if (event.type === "trace") {
            setStreamTrace(current => [...current, event.trace]);
            setActivePhase(phaseForTrace(event.trace.node));
          } else if (event.type === "result") {
            terminal = true; setResult(event.result); setStatus("success"); setActivePhase(4);
          } else {
            terminal = true; setStatus("error"); setError(event.error.message); setErrorCategory(event.error.category);
          }
        }
        if (done) break;
      }
      if (!terminal) throw new Error("流式连接提前结束，请重试。");
    } catch (caught) {
      setStatus("error"); setActivePhase(-1);
      setError(caught instanceof Error ? caught.message : "请求失败");
    } finally { setLoading(false); }
  }

  async function copySql() {
    if (result?.sql) await navigator.clipboard?.writeText(result.sql);
  }

  return <>
    <div className="ask-card">
      <div className="ask-card-head"><div><span className="ask-kicker">现在想了解什么？</span><strong>用一句话描述你的经营问题</strong></div><span className="ask-mode">{replay ? "静态演示" : selectedDataset?.source_type === "template" ? "演示模板" : "已上传数据"}</span></div>
      <div className="dataset-context">
        <label><span>当前数据</span><select aria-label="当前数据集" value={datasetId} onChange={event => changeDataset(event.target.value)} disabled={datasetLoading || loading}>{datasetLoading && <option>正在读取数据源…</option>}{datasets.map(item => <option value={item.id} key={item.id}>{item.name}</option>)}</select></label>
        <div><strong>{selectedDataset?.name ?? (datasetLoading ? "正在读取可用数据…" : "电商经营演示模板")}</strong><small>{selectedDataset?.description ?? "选择数据后，系统会根据字段自动推荐可问的问题。"}</small></div>
        <Link href="/data-sources">{replay ? "查看数据说明" : "接入新数据"} →</Link>
      </div>
      <div className="ask-row"><span className="ask-icon" aria-hidden="true">⌕</span><input aria-label="经营问题" value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => event.key === "Enter" && ask()} placeholder="例如：最近 30 天各区域 GMV" /><button className="ask-submit" onClick={() => ask()} disabled={loading}>{loading ? "分析中…" : "开始分析"}<span aria-hidden="true">↗</span></button></div>
      <div className="suggestions"><span>试试这样问</span>{suggestions.map(item => <button key={item} onClick={() => ask(item)} disabled={loading}>{item}</button>)}</div>
    </div>

    <div className={`query-status ${status}`} aria-live="polite">
      <div className="status-heading"><span className="status-dot" /><strong>{status === "idle" ? "准备好回答你的经营问题" : status === "running" ? "正在整理你的经营结果" : status === "success" ? "结果已生成，可以继续追问" : "这次分析没有完成"}</strong><small>{replay ? "示例数据 · 静态演示" : `${selectedDataset?.name ?? "Live API"} · 实时查询`}</small></div>
      <div className="phase-track">{phases.map(([id, label], index) => <div className={`phase ${(completedPhases.has(index) && activePhase > index) || status === "success" ? "done" : activePhase === index ? "active" : ""}`} key={id}><span>{completedPhases.has(index) && (activePhase > index || status === "success") ? "✓" : index + 1}</span>{label}</div>)}</div>
      {status === "running" && <div className="live-progress-note"><span className="live-indicator" />正在准备可信的结果与图表…</div>}
    </div>
    {error && <div className="error"><strong>无法完成这次问数 {errorCategory && <code>{errorCategory}</code>}</strong><span>{error}</span><small>可以换一个更明确的指标、时间范围或维度再试。</small></div>}
    {!result && displayTrace.length > 0 && status === "error" && <button className="technical-toggle failure-toggle" onClick={() => setShowTechnical(value => !value)}>{showTechnical ? "收起诊断详情" : "查看诊断详情"}</button>}
    {!result && displayTrace.length > 0 && status === "error" && showTechnical && <article className="card failure-trace"><div className="card-kicker"><h2>诊断详情</h2><span className="count-badge">{displayTrace.length} 个步骤</span></div><TraceList trace={displayTrace} expanded={expandedTrace} onExpand={node => setExpandedTrace(expandedTrace === node ? null : node)} /></article>}

    {result && <div className="result-grid">
      <article className="card answer-card"><div className="answer-card-head"><div><div className="card-kicker"><h2>经营结论</h2><span className="success-badge">{result.intent === "knowledge_query" ? "参考说明" : "已完成分析"}</span></div><p className="answer-label">基于当前数据范围整理</p></div><button className="technical-toggle" onClick={() => setShowTechnical(value => !value)}>{showTechnical ? "收起核验详情" : "查看核验详情"}</button></div><p className="answer">{result.answer}</p><div className="insight-box"><strong>{result.insight?.title ?? "简单分析"}</strong><p>{result.insight?.summary ?? result.answer}</p>{visibleHighlights.length > 0 && <ul>{visibleHighlights.map(item => <li key={item}>{item}</li>)}</ul>}</div>{result.chart.type !== "text" && <><MetricChart columns={result.columns} rows={result.rows} type={result.chart.type} /><div className="result-table"><div className="table-heading"><strong>结果明细</strong><small>{result.rows.length} 行 · {result.columns.join(" / ")}</small></div><table><thead><tr>{result.columns.map(column => <th key={column}>{column}</th>)}</tr></thead><tbody>{result.rows.slice(0, 8).map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={`${rowIndex}-${cellIndex}`}>{String(cell ?? "—")}</td>)}</tr>)}</tbody></table></div></>}</article>

      {showTechnical && <section className="technical-details" aria-label="核验详情"><div className="technical-heading"><div><span className="eyebrow">可选</span><h2>核验详情</h2></div><p>面向需要复核口径的产品、数据和研发人员。</p></div><div className="technical-grid"><article className="card"><div className="card-kicker"><h2>回答依据</h2><span className="count-badge">{result.retrieval_summary?.certified_hits ?? 0} 个认证源</span></div><p className="card-note">已使用 {result.retrieval_summary?.hits ?? result.evidence.length} 个相关知识片段辅助回答。</p><div className="evidence-list">{result.evidence.slice(0, 5).map(item => <button className="evidence-item" key={item.id} onClick={() => setExpandedEvidence(expandedEvidence === item.id ? null : item.id)}><span className="score">{item.score.toFixed(2)}</span><strong>{item.title}</strong><small>{item.type}</small>{expandedEvidence === item.id && <span className="evidence-detail">{item.match_reason ?? "已匹配相关业务知识"}。{item.text ? ` ${item.text}` : ""}</span>}</button>)}</div></article>

      <article className="card sql-card"><div className="card-kicker"><h2>{result.sql ? "查询明细" : "执行边界"}</h2>{result.sql && <button className="ghost-button" onClick={copySql}>复制 SQL</button>}</div>{result.sql ? <><div className="sql-meta"><span>只读查询</span><span>已通过安全校验</span><span>{result.entities?.time_range ?? "全部时间"}</span></div><pre>{result.sql}</pre></> : <div className="no-sql"><strong>本回答未执行数据查询</strong><span>这是基于业务知识的说明，不需要读取数据库。</span></div>}</article>

      <article className="card"><div className="card-kicker"><h2>处理过程</h2><span className="count-badge">耗时 {result.latency_ms} ms</span></div><TraceList trace={result.trace} expanded={expandedTrace} onExpand={node => setExpandedTrace(expandedTrace === node ? null : node)} /></article></div></section>}
    </div>}
  </>;
}
