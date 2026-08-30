"use client";

import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";

type Column = { name: string; type: string; nullable?: boolean; unique_count?: number; sample_values?: string[] };
type DatasetTable = { id: string; sheet_name: string; row_count: number; columns: Column[]; preview: Record<string, unknown>[] };
type Dataset = {
  id: string; name: string; source_type: "template" | "excel" | "csv"; status: string; description: string;
  row_count: number; table_count: number; created_at?: string | null; suggestions: string[]; tables?: DatasetTable[];
};

const replayDemo: Dataset = {
  id: "demo", name: "电商经营演示模板", source_type: "template", status: "ready",
  description: "内置电商示例，覆盖订单、客户、商品、渠道、营销和库存，用来体验完整智能问数链路。",
  row_count: 120, table_count: 6, created_at: null,
  suggestions: ["最近 30 天 GMV 是多少？", "最近 30 天各渠道退款率", "最近 30 天各活动 ROAS 排名", "今天各品类可用库存"],
  tables: [{ id: "demo.orders", sheet_name: "订单", row_count: 120, columns: [
    { name: "订单日期", type: "date" }, { name: "渠道", type: "text" }, { name: "区域", type: "text" }, { name: "成交金额", type: "real" },
  ], preview: [] }],
};

export default function DataSourceCenter() {
  const replay = process.env.NEXT_PUBLIC_DEMO_MODE === "replay";
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
  const inputRef = useRef<HTMLInputElement>(null);
  const [datasets, setDatasets] = useState<Dataset[]>(replay ? [replayDemo] : []);
  const [selected, setSelected] = useState<Dataset | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(!replay);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (replay) return;
    fetch(`${apiBase}/api/datasets`)
      .then(response => response.ok ? response.json() : Promise.reject(new Error(`数据源请求失败 (${response.status})`)))
      .then((payload: { items: Dataset[] }) => setDatasets(payload.items))
      .catch(caught => setError(caught instanceof Error ? caught.message : "无法读取数据源"))
      .finally(() => setLoading(false));
  }, [apiBase, replay]);

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const next = event.target.files?.[0] ?? null;
    setFile(next); setError(""); setMessage("");
    if (next && !name) setName(next.name.replace(/\.(xlsx|csv)$/i, ""));
  }

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file) { setError("请先选择一个 .xlsx 或 .csv 文件。"); return; }
    setUploading(true); setError(""); setMessage("");
    const body = new FormData(); body.append("file", file); body.append("name", name);
    try {
      const response = await fetch(`${apiBase}/api/datasets/upload`, { method: "POST", body });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.detail?.message ?? `上传失败 (${response.status})`);
      const created = payload as Dataset;
      setDatasets(current => [current[0] ?? replayDemo, created, ...current.slice(1).filter(item => item.id !== created.id)]);
      setSelected(created); setMessage(`“${created.name}”已完成字段识别，可以开始问数。`);
      window.dispatchEvent(new CustomEvent("chatbi:dataset-created", { detail: created }));
      setFile(null); setName(""); if (inputRef.current) inputRef.current.value = "";
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "上传失败");
    } finally { setUploading(false); }
  }

  async function inspect(dataset: Dataset) {
    if (dataset.tables || replay) { setSelected(dataset); return; }
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/datasets/${dataset.id}`);
      if (!response.ok) throw new Error(`数据画像读取失败 (${response.status})`);
      setSelected(await response.json() as Dataset);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "无法读取数据画像"); }
  }

  function startAsking(dataset: Dataset) {
    window.history.replaceState({}, "", `?dataset=${encodeURIComponent(dataset.id)}#ask`);
    window.dispatchEvent(new CustomEvent("chatbi:dataset-selected", { detail: dataset }));
    setSelected(null);
    document.getElementById("ask")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return <>
    <section className="source-layout">
      <form className={`upload-card ${replay ? "disabled" : ""}`} onSubmit={upload}>
        <div className="card-kicker"><h2>接入我的数据</h2><span className="count-badge">本地数据沙箱</span></div>
        <p>首行作为字段名，后续每行作为一条记录。支持多工作表 Excel，上传后自动生成字段画像和示例问题。</p>
        <button type="button" className="file-drop" onClick={() => !replay && inputRef.current?.click()} disabled={replay}>
          <span className="file-icon">↥</span>
          <strong>{file?.name ?? (replay ? "Replay 模式不上传文件" : "选择 Excel 或 CSV")}</strong>
          <small>{replay ? "请启动 Live 页面使用数据接入" : file ? `${(file.size / 1024).toFixed(1)} KB` : "最大 10 MB · .xlsx / .csv"}</small>
        </button>
        <input ref={inputRef} className="visually-hidden" type="file" accept=".xlsx,.csv" onChange={chooseFile} />
        <label className="source-name"><span>数据集名称</span><input value={name} onChange={event => setName(event.target.value)} placeholder="例如：2026 年销售明细" disabled={replay || uploading} /></label>
        <div className="upload-actions"><button type="submit" disabled={replay || uploading || !file}>{uploading ? "正在识别…" : "上传并识别"}</button><a href={`${basePath}/templates/sales-demo.csv`} download>下载 CSV 示例</a></div>
        <small className="privacy-note">原始文件不会写入 Git；当前 MVP 将标准化数据保存在本机、被 Git 忽略的 SQLite 文件中。</small>
      </form>

      <article className="source-boundary">
        <span className="eyebrow">上传提示</span><h2>让系统更准确理解你的数据</h2>
        <ul><li>第一行是清晰且唯一的字段名</li><li>日期、金额、数量保持同一列格式一致</li><li>一个工作表表达一类业务明细</li></ul>
        <p>上传后先检查系统识别的字段和样例，再使用自动生成的问题开始分析。原始文件不会进入 Git 仓库。</p>
      </article>
    </section>

    {message && <div className="source-message success">{message}</div>}
    {error && <div className="source-message failed">{error}</div>}

    <div className="source-list-head"><div><span className="eyebrow">Available datasets</span><h2>可用数据</h2></div><small>{loading ? "正在读取…" : `${datasets.length} 个数据集`}</small></div>
    <section className="source-grid">
      {datasets.map(dataset => <article className={`dataset-card ${dataset.source_type === "template" ? "template" : ""}`} key={dataset.id}>
        <div className="dataset-card-head"><span>{dataset.source_type === "template" ? "演示模板" : dataset.source_type.toUpperCase()}</span><i>可问数</i></div>
        <h3>{dataset.name}</h3><p>{dataset.description}</p>
        <div className="dataset-stats"><span><strong>{dataset.table_count}</strong> 张表</span><span><strong>{dataset.row_count.toLocaleString()}</strong> 行</span></div>
        <div className="dataset-questions"><small>可以这样问</small>{dataset.suggestions.slice(0, 3).map(item => <span key={item}>“{item}”</span>)}</div>
        <div className="dataset-actions"><button className="technical-toggle" onClick={() => inspect(dataset)}>查看数据画像</button><button className="dataset-start" onClick={() => startAsking(dataset)}>选择并提问 →</button></div>
      </article>)}
    </section>

    {selected && <div className="modal-backdrop" onClick={() => setSelected(null)}><article className="detail-modal dataset-modal" onClick={event => event.stopPropagation()}>
      <button className="close-button" onClick={() => setSelected(null)}>×</button><span className="eyebrow">Dataset profile</span><h2>{selected.name}</h2><p>{selected.description}</p>
      {selected.tables?.map(table => <section className="table-profile" key={table.id}><div><strong>{table.sheet_name}</strong><small>{table.row_count.toLocaleString()} 行 · {table.columns.length} 个字段</small></div><div className="column-chips">{table.columns.map(column => <span key={column.name}><b>{column.name}</b><small>{column.type}</small></span>)}</div>{table.preview.length > 0 && <div className="preview-table"><table><thead><tr>{Object.keys(table.preview[0]).map(key => <th key={key}>{key}</th>)}</tr></thead><tbody>{table.preview.slice(0, 5).map((row, index) => <tr key={index}>{Object.values(row).map((value, valueIndex) => <td key={valueIndex}>{String(value ?? "—")}</td>)}</tr>)}</tbody></table></div>}</section>)}
      <button className="modal-primary" onClick={() => startAsking(selected)}>使用这份数据开始问数 →</button>
    </article></div>}
  </>;
}
