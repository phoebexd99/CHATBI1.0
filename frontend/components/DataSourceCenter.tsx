"use client";

import { ChangeEvent, FormEvent, useEffect, useRef, useState } from "react";
import QueryWorkspace, { QueryDataset } from "./QueryWorkspace";

type ColumnRole = "time" | "measure" | "dimension" | "identifier";
type Column = { name: string; sql_name?: string; type: string; role?: ColumnRole; nullable?: boolean; non_null_ratio?: number; unique_count?: number; sample_values?: string[] };
type DatasetTable = { id: string; sheet_name: string; row_count: number; columns: Column[]; preview: Record<string, unknown>[] };
type Dataset = QueryDataset & { status: string; created_at?: string | null; tables?: DatasetTable[] };
type PostgresForm = { name: string; host: string; port: string; database: string; username: string; password: string; schema_name: string; sslmode: string };

const replayDemo: Dataset = {
  id: "demo", name: "电商经营演示模板", source_type: "template", status: "ready",
  description: "内置电商示例，覆盖订单、客户、商品、渠道、营销和库存，用来体验完整智能问数链路。",
  row_count: 120, table_count: 6, created_at: null,
  suggestions: ["最近 30 天 GMV 是多少？", "最近 30 天各渠道退款率", "最近 30 天各活动 ROAS 排名", "今天各品类可用库存"],
  tables: [{ id: "demo.orders", sheet_name: "订单", row_count: 120, columns: [
    { name: "订单日期", type: "date", role: "time" }, { name: "渠道", type: "text", role: "dimension" }, { name: "区域", type: "text", role: "dimension" }, { name: "成交金额", type: "real", role: "measure" },
  ], preview: [] }],
};

const roleLabels: Record<ColumnRole, string> = { time: "时间", measure: "指标", dimension: "维度", identifier: "标识" };

function inferredRole(column: Column): ColumnRole {
  if (column.role) return column.role;
  if (column.type === "date") return "time";
  if (["integer", "real"].includes(column.type)) return "measure";
  return "dimension";
}

export default function DataSourceCenter() {
  const replay = process.env.NEXT_PUBLIC_DEMO_MODE === "replay";
  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
  const inputRef = useRef<HTMLInputElement>(null);
  const [datasets, setDatasets] = useState<Dataset[]>(replay ? [replayDemo] : []);
  const [selected, setSelected] = useState<Dataset | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [databaseOpen, setDatabaseOpen] = useState(false);
  const [queryDataset, setQueryDataset] = useState<Dataset | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [datasetNameDraft, setDatasetNameDraft] = useState("");
  const [postgres, setPostgres] = useState<PostgresForm>({ name: "经营数据库", host: "", port: "5432", database: "", username: "", password: "", schema_name: "public", sslmode: "prefer" });
  const [loading, setLoading] = useState(!replay);
  const [uploading, setUploading] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [savingModel, setSavingModel] = useState(false);
  const [roleDrafts, setRoleDrafts] = useState<Record<string, ColumnRole>>({});
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const requestedDataset = new URLSearchParams(window.location.search).get("dataset");
    if (replay) {
      if (requestedDataset === replayDemo.id) setQueryDataset(replayDemo);
      return;
    }
    fetch(`${apiBase}/api/datasets`)
      .then(response => response.ok ? response.json() : Promise.reject(new Error(`数据源请求失败 (${response.status})`)))
      .then((payload: { items: Dataset[] }) => {
        setDatasets(payload.items);
        const requested = payload.items.find(item => item.id === requestedDataset);
        if (requested && requested.status !== "reconnect_required") setQueryDataset(requested);
      })
      .catch(caught => setError(caught instanceof Error ? caught.message : "无法读取数据源"))
      .finally(() => setLoading(false));
  }, [apiBase, replay]);

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const next = event.target.files?.[0] ?? null;
    setFile(next); setError(""); setMessage("");
    if (next && !name) setName(next.name.replace(/\.(xlsx|csv)$/i, ""));
  }

  function openProfile(dataset: Dataset) {
    const drafts: Record<string, ColumnRole> = {};
    dataset.tables?.forEach(table => table.columns.forEach(column => {
      if (column.sql_name) drafts[`${table.id}:${column.sql_name}`] = inferredRole(column);
    }));
    setRoleDrafts(drafts);
    setDatasetNameDraft(dataset.name);
    setSelected(dataset);
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
      openProfile(created); setMessage(`“${created.name}”已完成字段识别，请确认字段用途后开始问数。`);
      window.dispatchEvent(new CustomEvent("chatbi:dataset-created", { detail: created }));
      setFile(null); setName(""); if (inputRef.current) inputRef.current.value = "";
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "上传失败");
    } finally { setUploading(false); }
  }

  async function inspect(dataset: Dataset) {
    if (dataset.tables || replay) { openProfile(dataset); return; }
    setError("");
    try {
      const response = await fetch(`${apiBase}/api/datasets/${dataset.id}`);
      if (!response.ok) throw new Error(`数据画像读取失败 (${response.status})`);
      openProfile(await response.json() as Dataset);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "无法读取数据画像"); }
  }

  async function saveModel() {
    if (!selected?.tables || selected.source_type === "template") return;
    const columns = selected.tables.flatMap(table => table.columns.filter(column => column.sql_name).map(column => ({
      table_id: table.id, sql_name: column.sql_name as string,
      role: roleDrafts[`${table.id}:${column.sql_name}`] ?? inferredRole(column),
    })));
    setSavingModel(true); setError("");
    try {
      const response = await fetch(`${apiBase}/api/datasets/${selected.id}/model`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ columns, name: datasetNameDraft }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.detail?.message ?? `字段设置保存失败 (${response.status})`);
      const updated = payload as Dataset;
      setDatasets(current => current.map(item => item.id === updated.id ? { ...item, ...updated } : item));
      openProfile(updated);
      window.dispatchEvent(new CustomEvent("chatbi:dataset-selected", { detail: updated }));
      setMessage(`“${updated.name}”的字段用途已保存，推荐问题已同步更新。`);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "字段设置保存失败"); }
    finally { setSavingModel(false); }
  }

  async function connectDatabase(event: FormEvent) {
    event.preventDefault();
    setConnecting(true); setError(""); setMessage("");
    try {
      const response = await fetch(`${apiBase}/api/datasets/connect/postgresql`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...postgres, port: Number(postgres.port) }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload?.detail?.message ?? `数据库连接失败 (${response.status})`);
      const created = payload as Dataset;
      setDatasets(current => [current[0] ?? replayDemo, created, ...current.slice(1).filter(item => item.id !== created.id)]);
      setDatabaseOpen(false); openProfile(created);
      window.dispatchEvent(new CustomEvent("chatbi:dataset-created", { detail: created }));
      setMessage(`“${created.name}”已连接并读取到 ${created.table_count} 张表，请确认字段后开始问数。`);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "数据库连接失败"); }
    finally { setConnecting(false); }
  }

  function startAsking(dataset: Dataset) {
    if (dataset.status === "reconnect_required") {
      setError("该数据库连接的临时凭据已失效，请重新连接 PostgreSQL 后再问数。");
      setPickerOpen(false); setDatabaseOpen(true); return;
    }
    window.history.replaceState({}, "", `?dataset=${encodeURIComponent(dataset.id)}`);
    setSelected(null); setPickerOpen(false);
    setQueryDataset(dataset);
  }

  function closeQuery() {
    setQueryDataset(null);
    window.history.replaceState({}, "", window.location.pathname);
  }

  function changeQueryDataset() {
    closeQuery();
    setPickerOpen(true);
  }

  return <>
    <section className="source-entry-grid" aria-label="选择数据接入方式">
      <form className={`source-entry file-entry ${replay ? "disabled" : ""}`} onSubmit={upload}>
        <div className="source-entry-icon">XL</div><span className="eyebrow">Excel / CSV</span><h3>上传本地文件</h3>
        <p>适合销售明细、运营报表等文件；上传后自动识别字段并生成问题建议。</p>
        <button type="button" className="entry-action" onClick={() => !replay && inputRef.current?.click()} disabled={replay}>{file?.name ?? (replay ? "Live 模式可上传" : "选择文件")}</button>
        <input ref={inputRef} className="visually-hidden" type="file" accept=".xlsx,.csv" onChange={chooseFile} />
        {file && <><label className="source-name"><span>数据集名称</span><input value={name} onChange={event => setName(event.target.value)} placeholder="例如：销售数据" disabled={uploading} /></label><button type="submit" disabled={uploading}>{uploading ? "正在识别…" : "上传并识别"}</button></>}
        <a className="entry-help" href={`${basePath}/templates/sales-demo.csv`} download>下载 CSV 示例</a>
      </form>

      <article className={`source-entry database-entry ${replay ? "disabled" : ""}`}>
        <div className="source-entry-icon">DB</div><span className="eyebrow">PostgreSQL</span><h3>连接业务数据库</h3>
        <p>使用只读账号连接数据库，自动发现 Schema、数据表和字段，问数时直接查询源库。</p>
        <button className="entry-action" onClick={() => setDatabaseOpen(true)} disabled={replay}>配置数据库连接</button>
        <small className="entry-help">密码仅保留在当前 API 进程</small>
      </article>

      <article className="source-entry template-entry">
        <div className="source-entry-icon">DEMO</div><span className="eyebrow">No data required</span><h3>使用演示模板</h3>
        <p>先查看操作步骤，再从电商模板或已经接入的数据中选择一份开始提问。</p>
        <button className="entry-action" onClick={() => setPickerOpen(true)}>{loading ? "正在读取…" : "选择模板或已有数据"}</button>
        <small className="entry-help">当前有 {datasets.length} 份可选数据</small>
      </article>
    </section>

    {message && <div className="source-message success">{message}</div>}
    {error && <div className="source-message failed">{error}</div>}

    {pickerOpen && <div className="modal-backdrop" onClick={() => setPickerOpen(false)}><article className="detail-modal picker-modal" onClick={event => event.stopPropagation()}>
      <button className="close-button" onClick={() => setPickerOpen(false)}>×</button><span className="eyebrow">Quick start</span><h2>选择一份数据开始问数</h2>
      <div className="picker-steps"><div><span>1</span><strong>选择数据</strong><small>演示模板或已接入数据</small></div><div><span>2</span><strong>查看可问内容</strong><small>确认字段与推荐问题</small></div><div><span>3</span><strong>自然语言提问</strong><small>获得数字、图表和解读</small></div></div>
      <div className="picker-list">{datasets.map(dataset => <section className="picker-item" key={dataset.id}>
        <div><span className="source-type">{dataset.source_type === "template" ? "演示模板" : dataset.source_type === "postgresql" ? "数据库" : dataset.source_type.toUpperCase()}</span><h3>{dataset.name}</h3><p>{dataset.description}</p><small>{dataset.table_count} 张表 · {dataset.row_count.toLocaleString()} 行{dataset.status === "reconnect_required" ? " · 需要重新连接" : ""}</small></div>
        <div className="picker-questions">{dataset.suggestions.slice(0, 2).map(item => <span key={item}>“{item}”</span>)}</div>
        <div className="picker-actions"><button className="technical-toggle" onClick={() => inspect(dataset)}>查看字段</button><button onClick={() => startAsking(dataset)} disabled={dataset.status === "reconnect_required"}>选择并提问 →</button></div>
      </section>)}</div>
    </article></div>}

    {databaseOpen && <div className="modal-backdrop" onClick={() => !connecting && setDatabaseOpen(false)}><form className="detail-modal database-modal" onSubmit={connectDatabase} onClick={event => event.stopPropagation()}>
      <button type="button" className="close-button" onClick={() => setDatabaseOpen(false)}>×</button><span className="eyebrow">Read-only PostgreSQL</span><h2>连接业务数据库</h2><p>请使用只读数据库账号。平台只发现指定 Schema 中的表和字段，并且只执行通过安全校验的 SELECT。</p>
      <div className="connection-grid"><label className="wide-field"><span>连接名称</span><input value={postgres.name} onChange={event => setPostgres(current => ({ ...current, name: event.target.value }))} placeholder="例如：销售分析库" required /></label><label><span>主机</span><input value={postgres.host} onChange={event => setPostgres(current => ({ ...current, host: event.target.value }))} placeholder="db.example.com" required /></label><label><span>端口</span><input value={postgres.port} onChange={event => setPostgres(current => ({ ...current, port: event.target.value }))} inputMode="numeric" required /></label><label><span>数据库</span><input value={postgres.database} onChange={event => setPostgres(current => ({ ...current, database: event.target.value }))} placeholder="analytics" required /></label><label><span>Schema</span><input value={postgres.schema_name} onChange={event => setPostgres(current => ({ ...current, schema_name: event.target.value }))} required /></label><label><span>只读用户名</span><input value={postgres.username} onChange={event => setPostgres(current => ({ ...current, username: event.target.value }))} autoComplete="username" required /></label><label><span>密码</span><input type="password" value={postgres.password} onChange={event => setPostgres(current => ({ ...current, password: event.target.value }))} autoComplete="current-password" /></label><label className="wide-field"><span>SSL 模式</span><select value={postgres.sslmode} onChange={event => setPostgres(current => ({ ...current, sslmode: event.target.value }))}><option value="prefer">优先 SSL</option><option value="require">必须 SSL</option><option value="verify-full">校验证书与域名</option><option value="disable">不使用 SSL（仅限可信本地环境）</option></select></label></div>
      <div className="connection-note"><strong>凭据处理</strong><span>密码不会写入 Git、SQLite 元数据或浏览器存储；API 重启后需要重新连接。</span></div>
      <button type="submit" className="modal-primary" disabled={connecting}>{connecting ? "正在测试并发现数据表…" : "连接并读取数据表"}</button>
    </form></div>}

    {selected && <div className="modal-backdrop" onClick={() => setSelected(null)}><article className="detail-modal dataset-modal" onClick={event => event.stopPropagation()}>
      <button className="close-button" onClick={() => setSelected(null)}>×</button><span className="eyebrow">Dataset profile</span><label className="profile-name"><span>数据名称</span><input value={datasetNameDraft} onChange={event => setDatasetNameDraft(event.target.value)} disabled={selected.source_type === "template"} /></label><p>{selected.description}</p>
      <div className="role-guide"><span><i className="role-time" />时间：用于年月筛选和趋势</span><span><i className="role-measure" />指标：用于求和、平均和比较</span><span><i className="role-dimension" />维度：用于分类和筛选</span><span><i className="role-identifier" />标识：仅定位记录，不参与求和</span></div>
      {selected.tables?.map(table => <section className="table-profile" key={table.id}><div><strong>{table.sheet_name}</strong><small>{table.row_count.toLocaleString()} 行 · {table.columns.length} 个字段</small></div><div className="column-model-grid">{table.columns.map(column => { const key = `${table.id}:${column.sql_name}`; const role = roleDrafts[key] ?? inferredRole(column); return <label key={column.name}><span><b>{column.name}</b><small>{column.type} · 完整率 {Math.round((column.non_null_ratio ?? 1) * 100)}%</small></span>{selected.source_type === "template" || !column.sql_name ? <em>{roleLabels[role]}</em> : <select aria-label={`${column.name}字段用途`} value={role} onChange={event => setRoleDrafts(current => ({ ...current, [key]: event.target.value as ColumnRole }))}><option value="time">时间</option><option value="measure">指标</option><option value="dimension">维度</option><option value="identifier">标识</option></select>}</label>; })}</div>{table.preview.length > 0 && <div className="preview-table"><table><thead><tr>{Object.keys(table.preview[0]).map(key => <th key={key}>{key}</th>)}</tr></thead><tbody>{table.preview.slice(0, 5).map((row, index) => <tr key={index}>{Object.values(row).map((value, valueIndex) => <td key={valueIndex}>{String(value ?? "—")}</td>)}</tr>)}</tbody></table></div>}</section>)}
      <div className="model-actions">{selected.source_type !== "template" && <button className="technical-toggle" onClick={saveModel} disabled={savingModel}>{savingModel ? "保存中…" : "保存字段设置"}</button>}<button className="modal-primary" onClick={() => startAsking(selected)}>使用这份数据开始问数 →</button></div>
    </article></div>}

    {queryDataset && <div className="modal-backdrop query-backdrop" onClick={closeQuery}><article className="detail-modal query-workspace-modal" onClick={event => event.stopPropagation()}>
      <div className="query-modal-heading"><div><span className="eyebrow">Ask your data</span><h2>对“{queryDataset.name}”直接提问</h2><p>输入业务问题，平台会在当前窗口持续返回进度、数据结果、图表和简单解读。</p></div><button className="close-button" onClick={closeQuery} aria-label="关闭问数窗口">×</button></div>
      <QueryWorkspace initialDataset={queryDataset} onChangeData={changeQueryDataset} />
    </article></div>}
  </>;
}
