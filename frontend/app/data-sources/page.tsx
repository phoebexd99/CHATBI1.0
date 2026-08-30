import DataSourceCenter from "@/components/DataSourceCenter";

export default function DataSourcesPage() {
  const replay = process.env.NEXT_PUBLIC_DEMO_MODE === "replay";
  return <section className="page">
    <span className="mode-pill">{replay ? "Replay mode" : "Live data"}</span>
    <span className="eyebrow">Connect → profile → ask</span>
    <h1>先接入数据，<br />再直接问业务问题。</h1>
    <p className="lede">上传自己的 Excel 或 CSV，CHATBI 会识别工作表、字段类型和可分析维度；内置电商数据继续作为随时可用的演示模板。</p>
    <DataSourceCenter />
  </section>;
}
