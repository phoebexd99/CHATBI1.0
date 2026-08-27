import QueryWorkspace from "@/components/QueryWorkspace";

export default function QueryPage() {
  const mode = process.env.NEXT_PUBLIC_DEMO_MODE === "replay" ? "Replay mode" : "Live pipeline";
  return (
    <section className="page">
      <span className="mode-pill">{mode}</span>
      <span className="eyebrow">Ask → verify → decide</span>
      <h1>把经营问题，变成<br />可验证的答案。</h1>
      <p className="lede">基于认证指标、业务语义和已验证 SQL，给运营人员一个不需要懂 SQL 的可信问数入口。</p>
      <QueryWorkspace />
    </section>
  );
}

