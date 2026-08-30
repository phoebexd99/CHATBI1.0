import DataSourceCenter from "@/components/DataSourceCenter";
import QueryWorkspace from "@/components/QueryWorkspace";

export default function UnifiedQueryPage() {
  const replay = process.env.NEXT_PUBLIC_DEMO_MODE === "replay";
  return (
    <section className="page unified-page">
      <span className="mode-pill">{replay ? "Replay mode" : "Live workspace"}</span>
      <span className="eyebrow">Connect data → ask → get answers</span>
      <h1>上传你的数据，<br />用一句话得到分析结果。</h1>
      <p className="lede">不需要先懂数据库或 SQL。上传 Excel / CSV，或直接使用电商演示模板；选择数据后自然语言提问，平台会返回数字、图表、明细和简单解读。</p>
      <div className="hero-actions"><a href="#data-source">接入我的数据 ↓</a><a href="#ask" className="secondary">先用演示模板体验</a></div>

      <div className="core-flow" aria-label="平台核心流程">
        <div><span>1</span><strong>接入数据</strong><small>上传 Excel / CSV，或选择模板</small></div>
        <i>→</i><div><span>2</span><strong>自然语言提问</strong><small>直接描述想看的指标或分析</small></div>
        <i>→</i><div><span>3</span><strong>获得业务结果</strong><small>数字、图表、明细与简单解读</small></div>
      </div>

      <section className="flow-section" id="data-source">
        <div className="flow-section-head"><span>第一步</span><div><h2>选择要分析的数据</h2><p>没有自己的文件也没关系，可以直接使用内置电商模板体验。</p></div></div>
        <DataSourceCenter />
      </section>

      <section className="flow-section ask-section" id="ask">
        <div className="flow-section-head"><span>第二步</span><div><h2>对选中的数据直接提问</h2><p>平台会根据字段推荐可问的问题，也可以输入自己的业务问题。</p></div></div>
        <QueryWorkspace />
      </section>
    </section>
  );
}

