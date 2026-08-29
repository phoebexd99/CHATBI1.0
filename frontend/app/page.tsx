import QueryWorkspace from "@/components/QueryWorkspace";

export default function QueryPage() {
  const mode = process.env.NEXT_PUBLIC_DEMO_MODE === "replay" ? "Replay mode" : "Live pipeline";
  return (
    <section className="page">
      <span className="mode-pill">{mode}</span>
      <span className="eyebrow">Ask → understand → decide</span>
      <h1>先问一个问题，<br />马上看懂经营结果。</h1>
      <p className="lede">不用写 SQL。用自然语言提问，获得清晰的数字、图表和下一步分析建议；需要复核时，再展开回答依据。</p>
      <QueryWorkspace />
    </section>
  );
}

