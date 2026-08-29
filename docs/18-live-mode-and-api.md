# Live 模式与 API 接入

## Live 页面怎么打开

Live 页面不是 GitHub Pages 地址。GitHub Pages 只能运行 Replay 静态模式；Live 页面需要本机同时运行 FastAPI、前端和 SSH 到 PostgreSQL 的本地隧道。

### 推荐方式

1. 在仓库根目录准备本地 `.env`。不要提交该文件，也不要把数据库口令发到聊天中。
2. 确认 `.env` 中使用以下非敏感运行配置：

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_DEMO_MODE=live
CHATBI_DATA_PROFILE=olist
```

3. `DATABASE_URL` 应指向本机 SSH 隧道端口 `127.0.0.1:15432`，不要直接指向云服务器公网地址。SSH 参数使用 `.env.example` 中的占位配置，私钥保存在仓库外。
4. 启动：

```powershell
.\scripts\start-local.ps1
```

5. 打开 <http://localhost:3000/>。页面顶部显示“Live pipeline”，提问框提交后会调用本机 FastAPI，再通过 SSE 接收结果。

停止服务：

```powershell
.\scripts\stop-local.ps1
```

如果修改了 `NEXT_PUBLIC_*`，需要重启 Next.js，因为这类变量会在前端启动/构建时注入。

## API 链路

```text
浏览器 http://localhost:3000
  → POST http://localhost:8000/api/query/stream
  → FastAPI / LangGraph workflow
  → semantic catalog + retrieval + Wren adapter
  → SQL safety gate
  → PostgreSQL Olist Mart
  → Server-Sent Events
  → 页面结果、图表和业务洞察
```

核心接口：

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/api/health` | 检查 API、数据库和语义适配器状态 |
| POST | `/api/query` | 获取一次性 JSON 结果 |
| POST | `/api/query/stream` | 获取节点过程事件和最终结果的 SSE 流 |
| GET | `/api/knowledge` | 读取知识中心内容 |
| GET | `/api/metrics` | 读取当前指标目录 |
| GET | `/api/evals` | 读取评测题和最近一次评测结果 |

## 手动验证 API

检查健康状态：

```powershell
Invoke-RestMethod http://localhost:8000/api/health | ConvertTo-Json
```

一次性 JSON 问数：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://localhost:8000/api/query `
  -ContentType 'application/json' `
  -Body '{"question":"2017年11月Olist商品成交额是多少？"}' | ConvertTo-Json -Depth 8
```

SSE 流式问数：

```powershell
curl.exe -N -X POST http://localhost:8000/api/query/stream `
  -H "Content-Type: application/json" `
  -d "{\"question\":\"最近 30 天 GMV 是多少？\"}"
```

正常 SSE 会先返回多个 `type=trace` 事件，最后返回一个 `type=result` 事件。前端默认不展示这些内部节点名称；它只展示“理解问题、确认口径、分析数据、生成结论”四段面向业务的状态。需要研发或数据人员排查时，才点击结果中的“查看核验详情”。

## 常见问题

- 页面显示 Replay：检查 `NEXT_PUBLIC_DEMO_MODE` 是否为 `live`，并重启前端。
- 页面请求失败：先访问 `/api/health`，确认 API 进程和数据库隧道均正常。
- 返回 `422`：通常表示问题超出当前指标或安全边界，应换成 Olist 支持的指标、时间范围和维度。
- API 健康但 Olist 查询失败：确认 `CHATBI_DATA_PROFILE=olist`、`DATABASE_URL` 指向隧道端口，并且云端已存在 `chatbi_raw/chatbi_mart/chatbi_meta`。
- GitHub Pages 无法直接切换 Live：静态站点没有 FastAPI 和 PostgreSQL 网络权限；Live 必须在本机或后续受控服务器环境运行。

