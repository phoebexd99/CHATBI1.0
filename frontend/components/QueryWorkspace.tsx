"use client";

import { useState } from "react";
import MetricChart from "./MetricChart";

type Result = {
  answer: string; sql: string; columns: string[]; rows: unknown[][]; chart: { type: string };
  evidence: { id: string; type: string; title: string; score: number; keyword_score: number; vector_score: number }[];
  trace: { node: string; status: string; duration_ms: number }[]; latency_ms: number;
};

const suggestions = ["最近 30 天 GMV 是多少？", "最近 30 天各区域 GMV", "按渠道看近 30 天 GMV"];

export default function QueryWorkspace() {
  const [question, setQuestion] = useState(suggestions[0]);
  const [result, setResult] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const replay = process.env.NEXT_PUBLIC_DEMO_MODE === "replay";
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

  async function ask(nextQuestion = question) {
    setLoading(true); setError(""); setQuestion(nextQuestion);
    try {
      const response = replay
        ? await fetch(`${basePath}/replay/recent-30d-gmv.json`)
        : await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/query`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: nextQuestion }) });
      if (!response.ok) throw new Error(`请求失败 (${response.status})`);
      setResult(await response.json());
    } catch (caught) { setError(caught instanceof Error ? caught.message : "请求失败"); }
    finally { setLoading(false); }
  }

  return <>
    <div className="ask-card">
      <div className="ask-row"><input aria-label="经营问题" value={question} onChange={event => setQuestion(event.target.value)} onKeyDown={event => event.key === "Enter" && ask()} /><button onClick={() => ask()} disabled={loading}>{loading ? "分析中…" : "开始问数"}</button></div>
      <div className="suggestions">{suggestions.map(item => <button key={item} onClick={() => ask(item)}>{item}</button>)}</div>
    </div>
    {error && <div className="error">{error}</div>}
    {result && <div className="result-grid">
      <article className="card"><h2>经营结论</h2><p className="answer">{result.answer}</p><MetricChart columns={result.columns} rows={result.rows} type={result.chart.type} /></article>
      <article className="card"><h2>检索证据</h2><div className="evidence-list">{result.evidence.slice(0, 4).map(item => <div className="evidence-item" key={item.id}><span className="score">{item.score.toFixed(2)}</span><strong>{item.title}</strong><small>{item.type} · keyword {item.keyword_score.toFixed(2)} · vector {item.vector_score.toFixed(2)}</small></div>)}</div></article>
      <article className="card"><h2>安全 SQL</h2><pre>{result.sql}</pre></article>
      <article className="card"><h2>工作流 Trace · {result.latency_ms} ms</h2><div className="trace-list">{result.trace.map((item, index) => <div className="trace-item" key={item.node}><span className="trace-index">{index + 1}</span><span>{item.node}</span><span className="trace-ms">{item.duration_ms} ms</span></div>)}</div></article>
    </div>}
  </>;
}

