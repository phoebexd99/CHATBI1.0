"use client";

import { useMemo, useState } from "react";
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

const liveSuggestions = [
  "最近 30 天 GMV 是多少？",
  "最近 30 天各渠道退款率",
  "最近 30 天各活动 ROAS 排名",
  "开学季最近 30 天下单转化率",
  "今天各品类可用库存",
  "ROAS 的定义是什么？",
];
const replaySuggestions = ["最近 30 天 GMV 是多少？"];
const phases = [
  ["interpret", "理解问题"], ["retrieve", "检索知识"], ["plan", "生成语义计划"],
  ["validate", "安全校验 SQL"], ["execute", "执行并生成洞察"],
];

function phaseForTrace(node: string): number {
  if (["classify", "extract_entities", "check_ambiguity"].includes(node)) return 0;
  if (node === "retrieve") return 1;
  if (["semantic_plan", "generate_sql"].includes(node)) return 2;
  if (["safety", "dry_run", "repair_once"].includes(node)) return 3;
  return 4;
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
  const [expandedEvidence, setExpandedEvidence] = useState<string | null>(null);
  const [expandedTrace, setExpandedTrace] = useState<string | null>(null);
  const replay = process.env.NEXT_PUBLIC_DEMO_MODE === "replay";
  const suggestions = replay ? replaySuggestions : liveSuggestions;
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
  const displayTrace = result?.trace ?? streamTrace;

  const completedPhases = useMemo<Set<number>>(() => new Set<number>(displayTrace.filter(item => item.status !== "error").map(item => phaseForTrace(item.node))), [displayTrace]);

  async function ask(nextQuestion = question) {
    const trimmed = nextQuestion.trim();
    if (!trimmed) { setError("先输入一个经营问题。"); return; }
    setLoading(true); setStatus("running"); setError(""); setErrorCategory(""); setQuestion(trimmed);
    setResult(null); setStreamTrace([]); setActivePhase(0); setExpandedEvidence(null); setExpandedTrace(null);
    try {
      if (replay) {
        const response = await fetch(`${basePath}/replay/recent-30d-gmv.json`);
        if (!response.ok) throw new Error(`Replay fixture 请求失败 (${response.status})`);
        const next = await response.json() as Result;
        setStreamTrace(next.trace); setResult(next); setStatus("success"); setActivePhase(4);
        return;
      }
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/query/stream`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: trimmed }),
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
      <div className="ask-row"><input aria-label="经营问题" value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => event.key === "Enter" && ask()} placeholder="例如：最近 30 天各区域 GMV" /><button onClick={() => ask()} disabled={loading}>{loading ? "分析中…" : "开始问数"}</button></div>
      <div className="suggestions">{suggestions.map(item => <button key={item} onClick={() => ask(item)} disabled={loading}>{item}</button>)}</div>
    </div>

    <div className={`query-status ${status}`} aria-live="polite">
      <div className="status-heading"><span className="status-dot" /><strong>{status === "idle" ? "等待一个经营问题" : status === "running" ? "正在接收真实工作流事件" : status === "success" ? "答案已完成，可继续核验" : "这次问题没有完成"}</strong><small>{replay ? "Replay fixture · 静态只读" : "Live SSE · LangGraph 逐节点 Trace"}</small></div>
      <div className="phase-track">{phases.map(([id, label], index) => <div className={`phase ${(completedPhases.has(index) && activePhase > index) || status === "success" ? "done" : activePhase === index ? "active" : ""}`} key={id}><span>{completedPhases.has(index) && (activePhase > index || status === "success") ? "✓" : index + 1}</span>{label}</div>)}</div>
      {status === "running" && streamTrace.length > 0 && <div className="live-trace-strip"><span className="live-indicator" />已收到 {streamTrace.length} 个节点事件 · 当前：{streamTrace.at(-1)?.node}</div>}
    </div>
    {error && <div className="error"><strong>无法完成这次问数 {errorCategory && <code>{errorCategory}</code>}</strong><span>{error}</span><small>可以换一个更明确的指标、时间范围或维度再试。</small></div>}
    {!result && displayTrace.length > 0 && status === "error" && <article className="card failure-trace"><div className="card-kicker"><h2>失败 Trace</h2><span className="count-badge">{displayTrace.length} 个节点</span></div><TraceList trace={displayTrace} expanded={expandedTrace} onExpand={node => setExpandedTrace(expandedTrace === node ? null : node)} /></article>}

    {result && <div className="result-grid">
      <article className="card answer-card"><div className="card-kicker"><h2>经营结论</h2><span className="success-badge">{result.intent === "knowledge_query" ? "证据回答" : "已验证"}</span></div><p className="answer">{result.answer}</p><div className="insight-box"><strong>{result.insight?.title ?? "洞察"}</strong><p>{result.insight?.summary ?? result.answer}</p>{result.insight?.highlights && <ul>{result.insight.highlights.map(item => <li key={item}>{item}</li>)}</ul>}</div>{result.chart.type !== "text" && <><MetricChart columns={result.columns} rows={result.rows} type={result.chart.type} /><div className="result-table"><div className="table-heading"><strong>结果明细</strong><small>{result.rows.length} 行 · {result.columns.join(" / ")}</small></div><table><thead><tr>{result.columns.map(column => <th key={column}>{column}</th>)}</tr></thead><tbody>{result.rows.slice(0, 8).map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={`${rowIndex}-${cellIndex}`}>{String(cell ?? "—")}</td>)}</tr>)}</tbody></table></div></>}</article>

      <article className="card"><div className="card-kicker"><h2>RAG 命中</h2><span className="count-badge">{result.retrieval_summary?.certified_hits ?? 0} 个认证源</span></div><p className="card-note">{result.retrieval_summary?.hits ?? result.evidence.length} 个候选知识片段，Top score {Number(result.retrieval_summary?.top_score ?? result.evidence[0]?.score ?? 0).toFixed(2)}</p><div className="evidence-list">{result.evidence.slice(0, 5).map(item => <button className="evidence-item" key={item.id} onClick={() => setExpandedEvidence(expandedEvidence === item.id ? null : item.id)}><span className="score">{item.score.toFixed(2)}</span><strong>{item.title}</strong><small>{item.type} · keyword {item.keyword_score.toFixed(2)} · vector {item.vector_score.toFixed(2)}</small><div className="score-bar"><i style={{ width: `${Math.min(100, item.score * 100)}%` }} /></div>{expandedEvidence === item.id && <span className="evidence-detail">{item.match_reason ?? "关键词与向量特征共同命中"}。{item.text ? ` ${item.text}` : ""}</span>}</button>)}</div></article>

      <article className="card sql-card"><div className="card-kicker"><h2>{result.sql ? "安全 SQL" : "执行边界"}</h2>{result.sql && <button className="ghost-button" onClick={copySql}>复制 SQL</button>}</div>{result.sql ? <><div className="sql-meta"><span>只读 SELECT</span><span>allow-list + dry-run</span><span>{result.entities?.time_range ?? "all_time"}</span></div><pre>{result.sql}</pre></> : <div className="no-sql"><strong>本回答未执行 SQL</strong><span>知识问答直接由检索证据生成，数据库节点在 Trace 中标记为 skipped。</span></div>}</article>

      <article className="card"><div className="card-kicker"><h2>工作流 Trace</h2><span className="count-badge">{result.latency_ms} ms</span></div><TraceList trace={result.trace} expanded={expandedTrace} onExpand={node => setExpandedTrace(expandedTrace === node ? null : node)} /></article>
    </div>}
  </>;
}
