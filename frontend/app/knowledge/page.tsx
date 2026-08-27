const items = [
  ["metric", "认证指标：GMV", "汇总 paid 和 refunded 订单 gross_amount；取消订单不计入，退款额不从 GMV 扣减。"],
  ["schema", "订单事实表", "订单日期、状态、渠道、区域、成交额、优惠额与退款额构成最小经营分析模型。"],
  ["term", "业务术语：有效订单", "paid 与 refunded 为有效订单，cancelled 不进入认证经营指标。"],
  ["verified NL–SQL", "已验证问法：近 30 天 GMV", "认证口径、日期窗口和 SQL 均经过基准用例确认，可作为语义规划证据。"],
];

export default function KnowledgePage() {
  return <section className="page"><span className="eyebrow">Context service</span><h1>知识不是附件，<br />而是答案的证据。</h1><p className="lede">统一管理 Schema、认证指标、业务术语和已验证 NL–SQL，让每次回答都能追溯“为什么这样算”。</p><div className="stats"><div className="stat"><b>3</b><span>Schema 文档</span></div><div className="stat"><b>4</b><span>认证指标</span></div><div className="stat"><b>2</b><span>业务术语</span></div><div className="stat"><b>2</b><span>验证问法</span></div></div><div className="knowledge-grid">{items.map(([type, title, text]) => <article className="knowledge-card" key={title}><span className="type">{type}</span><h3>{title}</h3><p>{text}</p></article>)}</div></section>;
}

