"use client";

import { useEffect, useMemo, useState } from "react";

type KnowledgeItem = { id: string; type: string; title: string; text: string; tags?: string[]; sql?: string };
const seedItems: KnowledgeItem[] = [
  { id: "metric.gmv", type: "metric", title: "认证指标：GMV", text: "GMV 又称成交总额，汇总 paid 和 refunded 状态订单的 gross_amount；cancelled 不计入，refund_amount 不从 GMV 扣减。支持按日期、区域和渠道切分。", tags: ["GMV", "成交总额", "销售额"] },
  { id: "schema.orders", type: "schema", title: "订单事实表", text: "orders 每行一笔订单。字段包括 order_id, customer_id, order_date, status, channel, region, gross_amount, discount_amount, refund_amount。日期字段为 order_date。", tags: ["订单", "schema", "日期"] },
  { id: "term.valid_order", type: "term", title: "业务术语：有效订单", text: "有效订单包含 paid 和 refunded，不包含 cancelled。", tags: ["有效订单", "状态"] },
  { id: "verified.gmv_30d", type: "verified_nl_sql", title: "已验证问法：最近 30 天 GMV", text: "问题：最近 30 天 GMV 是多少？语义：按认证 GMV 口径，对最近 30 天有效订单汇总 gross_amount。", tags: ["GMV", "最近30天"], sql: "SELECT ROUND(SUM(gross_amount), 2) AS gmv FROM orders WHERE status IN ('paid', 'refunded')" },
  { id: "metric.refund_rate", type: "metric", title: "认证指标：退款率", text: "退款率等于退款金额除以 GMV，按百分比展示，用于监控售后损失。", tags: ["退款率", "退款占比", "售后"] },
  { id: "metric.roas", type: "metric", title: "认证指标：ROAS", text: "ROAS 等于归因收入除以广告花费；大于 1 表示归因收入高于投放成本，但不等同于利润。", tags: ["ROAS", "投产比", "营销"] },
  { id: "metric.stockout_rate", type: "metric", title: "认证指标：缺货率", text: "缺货率等于缺货商品数除以库存快照中的商品总数。", tags: ["缺货率", "库存", "供应链"] },
];
const typeLabels: Record<string, string> = { all: "全部", metric: "认证指标", schema: "Schema", term: "业务术语", verified_nl_sql: "验证问法" };

export default function KnowledgePage() {
  const [items, setItems] = useState<KnowledgeItem[]>(seedItems);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");
  const [selected, setSelected] = useState<KnowledgeItem | null>(null);
  const replay = process.env.NEXT_PUBLIC_DEMO_MODE === "replay";

  useEffect(() => {
    if (replay) return;
    fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/knowledge`)
      .then(response => response.ok ? response.json() : Promise.reject(new Error("knowledge unavailable")))
      .then(data => setItems(data.items ?? seedItems))
      .catch(() => setItems(seedItems));
  }, [replay]);

  const filtered = useMemo(() => items.filter(item => {
    const matchesType = filter === "all" || item.type === filter;
    const haystack = `${item.title} ${item.text} ${(item.tags ?? []).join(" ")}`.toLowerCase();
    return matchesType && haystack.includes(query.trim().toLowerCase());
  }), [filter, items, query]);
  const counts = useMemo(() => Object.fromEntries(Object.keys(typeLabels).map(type => [type, type === "all" ? items.length : items.filter(item => item.type === type).length])), [items]);

  return <section className="page"><span className="eyebrow">Context service</span><h1>知识不是附件，<br />而是答案的证据。</h1><p className="lede">统一管理 Schema、认证指标、业务术语和已验证 NL–SQL，让每次回答都能追溯“为什么这样算”。</p>
    <div className="stats">{[[counts.all, "知识片段"], [counts.metric, "认证指标"], [counts.term, "业务术语"], [counts.verified_nl_sql, "验证问法"]].map(([value, label]) => <div className="stat" key={label}><b>{value}</b><span>{label}</span></div>)}</div>
    <div className="toolbar"><label className="search-field"><span>⌕</span><input aria-label="搜索知识" placeholder="搜索指标、字段或业务术语" value={query} onChange={event => setQuery(event.target.value)} /></label><div className="filter-tabs">{Object.entries(typeLabels).map(([key, label]) => <button className={filter === key ? "selected" : ""} key={key} onClick={() => setFilter(key)}>{label}<small>{counts[key]}</small></button>)}</div></div>
    <div className="knowledge-result-head"><strong>{filtered.length} 个匹配结果</strong><span>{replay ? "Replay catalog · 静态只读" : "Live catalog · API-backed"}</span></div>
    <div className="knowledge-grid">{filtered.map(item => <article className="knowledge-card" key={item.id}><div className="knowledge-card-head"><span className="type">{typeLabels[item.type] ?? item.type}</span><span className="knowledge-id">{item.id}</span></div><h3>{item.title}</h3><p>{item.text}</p><div className="tag-list">{(item.tags ?? []).slice(0, 4).map(tag => <span key={tag}>{tag}</span>)}</div><button className="text-button" onClick={() => setSelected(item)}>查看证据详情 →</button></article>)}</div>
    {!filtered.length && <div className="empty-state"><strong>没有找到匹配的知识</strong><span>试试“GMV”“退款”或“order_date”。</span></div>}
    {selected && <div className="modal-backdrop" role="presentation" onClick={() => setSelected(null)}><article className="detail-modal" role="dialog" aria-modal="true" onClick={event => event.stopPropagation()}><div className="card-kicker"><span className="type">{typeLabels[selected.type] ?? selected.type}</span><button className="close-button" onClick={() => setSelected(null)} aria-label="关闭">×</button></div><h2>{selected.title}</h2><p>{selected.text}</p>{selected.tags && <div className="tag-list">{selected.tags.map(tag => <span key={tag}>{tag}</span>)}</div>}{selected.sql && <><h3>关联 SQL</h3><pre>{selected.sql}</pre></>}</article></div>}
  </section>;
}
