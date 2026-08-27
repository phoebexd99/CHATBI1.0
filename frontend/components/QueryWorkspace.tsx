"use client";

import { useEffect, useMemo, useState } from "react";
import MetricChart from "./MetricChart";

type Evidence = {
  id: string; type: string; title: string; text?: string; score: number;
  keyword_score: number; vector_score: number; match_reason?: string;
};
type TraceItem = { node: string; status: string; duration_ms: number };
type Result = {
  question: string; answer: string; sql: string; columns: string[]; rows: unknown[][];
  chart: { type: string; x?: string | null; y?: string };
  evidence: Evidence[]; trace: TraceItem[]; latency_ms: number;
  insight?: { title?: string; summary?: string; highlights?: string[] };
  retrieval_summary?: { hits?: number; top_score?: number; certified_hits?: number };
  entities?: { metric?: string; dimensions?: string[]; time_range?: string; filters?: Record<string, string | string[]> };
};

const suggestions = ["最近 30 天 GMV 是多少？", "最近 30 天各区域 GMV", "按渠道看近 30 天 GMV", "最近 30 天净收入是多少？"];
const phases = [
  ["interpret", "理解问题"], ["retrieve", "检索知识"], ["plan", "生成语义计划"],
  ["validate", "安全校验 SQL"], ["execute", "执行并生成洞察"],
];

function phaseForTrace(node: string) {
  if (["classify", "extract_entities", "check_ambiguity"].includes(node)) return 0;
  if (node === "retrieve") return 1;
  if (["semantic_plan", "generate_sql"].includes(node)) return 2;
  if (["safety", "dry_run", "repair_once"].includes(node)) return 3;
  return 4;
}

export default function QueryWorkspace() {
  const [question, setQuestion] = useState(suggestions[0]);
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState<"idle" | "running" | "success" | "error">("idle");
  const [activePhase, setActivePhase] = useState(-1);
  const [expandedEvidence, setExpandedEvidence] = useState<string | null>(null);
  const [expandedTrace, setExpandedTrace] = useState<string | null>(null);
  const replay = process.env.NEXT_PUBLIC_DEMO_MODE === "replay";
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

  useEffect(() => {
    if (!loading) return;
    setActivePhase(0);
    const timers = phases.slice(1).map((_, index) => window.setTimeout(() => setActivePhase(index + 1), (index + 1) * 420));
    return () => timers.forEach(window.clearTimeout);
  }, [loading]);

  const completedPhases = useMemo(() => {
    if (!result) return new Set<number>();
    return new Set(result.trace.map(item => phaseForTrace(item.node)));
  }, [result]);

  async function ask(nextQuestion = question) {
    const trimmed = nextQuestion.trim();
    if (!trimmed) { setError("先输入一个经营问题。"); return; }
    setLoading(true); setStatus("running"); setError(""); setQuestion(trimmed); setExpandedEvidence(null); setExpandedTrace(null);
    try {
      const response = replay
        ? await fetch(`${basePath}/replay/recent-30d-gmv.json`)
        : await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/query`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: trimmed }) });
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail?.message ?? `请求失败 (${response.status})`);
      }
      const next = await response.json() as Result;
      setResult(next); setStatus("success"); setActivePhase(4);
    } catch (caught) {
      setResult(null); setStatus("error"); setActivePhase(-1);
      setError(caught instanceof Error ? caught.message : "请求失败");
    } finally { setLoading(false); }
  }

  async function copySql() {
    if (result?.sql) await navigator.clipboard?.writeText(result.sql);
  }

  return <>
    <div className="ask-card">
      <div className="ask-row"><input aria-label="经营问题" value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => event.key === "Enter" && ask()} placeholder="例如：最近 30 天各区域 GMV" /><button onClick={() => ask()} disabled={loading}>{loading ? "分析中…" : "开始问数"}</button></div>
      <div className="suggestions">{suggestions.map(item => <button key={item} onClick={() => ask(item)} disabled={loading}>{item}</button>)}</div>
    </div>

    <div className={`query-status ${status}`} aria-live="polite">
      <div className="status-heading"><span className="status-dot" /><strong>{status === "idle" ? "等待一个经营问题" : status === "running" ? "正在生成可验证答案" : status === "success" ? "答案已完成，可继续核验" : "这次问题没有完成"}</strong><small>{replay ? "Replay fixture · 静态只读" : "Live pipeline · FastAPI → workflow → DB"}</small></div>
      <div className="phase-track">{phases.map(([id, label], index) => <div className={`phase ${completedPhases.has(index) || activePhase > index ? "done" : activePhase === index ? "active" : ""}`} key={id}><span>{completedPhases.has(index) || activePhase > index ? "✓" : index + 1}</span>{label}</div>)}</div>
    </div>
    {error && <div className="error"><strong>无法完成这次问数</strong><span>{error}</span><small>可以换一个更明确的指标、时间范围或维度再试。</small></div>}

    {result && <div className="result-grid">
      <article className="card answer-card"><div className="card-kicker"><h2>经营结论</h2><span className="success-badge">已验证</span></div><p className="answer">{result.answer}</p><div className="insight-box"><strong>{result.insight?.title ?? "洞察"}</strong><p>{result.insight?.summary ?? result.answer}</p>{result.insight?.highlights && <ul>{result.insight.highlights.map(item => <li key={item}>{item}</li>)}</ul>}</div><MetricChart columns={result.columns} rows={result.rows} type={result.chart.type} /><div className="result-table"><div className="table-heading"><strong>结果明细</strong><small>{result.rows.length} 行 · {result.columns.join(" / ")}</small></div><table><thead><tr>{result.columns.map(column => <th key={column}>{column}</th>)}</tr></thead><tbody>{result.rows.slice(0, 8).map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={`${rowIndex}-${cellIndex}`}>{String(cell ?? "—")}</td>)}</tr>)}</tbody></table></div></article>

      <article className="card"><div className="card-kicker"><h2>RAG 命中</h2><span className="count-badge">{result.retrieval_summary?.certified_hits ?? 0} 个认证源</span></div><p className="card-note">{result.retrieval_summary?.hits ?? result.evidence.length} 个候选知识片段，Top score {Number(result.retrieval_summary?.top_score ?? result.evidence[0]?.score ?? 0).toFixed(2)}</p><div className="evidence-list">{result.evidence.slice(0, 5).map(item => <button className="evidence-item" key={item.id} onClick={() => setExpandedEvidence(expandedEvidence === item.id ? null : item.id)}><span className="score">{item.score.toFixed(2)}</span><strong>{item.title}</strong><small>{item.type} · keyword {item.keyword_score.toFixed(2)} · vector {item.vector_score.toFixed(2)}</small><div className="score-bar"><i style={{ width: `${Math.min(100, item.score * 100)}%` }} /></div>{expandedEvidence === item.id && <span className="evidence-detail">{item.match_reason ?? "关键词与向量特征共同命中"}。{item.text ? ` ${item.text}` : ""}</span>}</button>)}</div></article>

      <article className="card sql-card"><div className="card-kicker"><h2>安全 SQL</h2><button className="ghost-button" onClick={copySql}>复制 SQL</button></div><div className="sql-meta"><span>只读 SELECT</span><span>allow-list + dry-run</span><span>{result.entities?.time_range ?? "all_time"}</span></div><pre>{result.sql}</pre></article>

      <article className="card"><div className="card-kicker"><h2>工作流 Trace</h2><span className="count-badge">{result.latency_ms} ms</span></div><div className="trace-list">{result.trace.map((item, index) => <button className="trace-item" key={`${item.node}-${index}`} onClick={() => setExpandedTrace(expandedTrace === item.node ? null : item.node)}><span className="trace-index">{index + 1}</span><span className="trace-node"><strong>{item.node}</strong>{expandedTrace === item.node && <small>{item.status === "ok" ? "节点完成，结果已写入共享状态" : `节点状态：${item.status}`}</small>}</span><span className="trace-ms">{item.duration_ms} ms</span></button>)}</div></article>
    </div>}
  </>;
}
