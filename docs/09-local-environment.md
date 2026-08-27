# 本地环境持久化运行

CHATBI 的本地真实链路使用腾讯云 PostgreSQL，但数据库只监听云服务器的 `127.0.0.1:5432`。本机通过 SSH 本地转发访问它；数据库端口不会暴露到公网。

## 一次性配置

1. 确认私钥文件存在于 `C:\Users\ivychen\.ssh\codexssh.pem`（或修改 `.env` 中的 `SSH_KEY_PATH`）。
2. 首次运行：

   ```powershell
   .\scripts\setup-local.ps1
   ```

   脚本会创建/复用 `.venv`、安装后端依赖、检查 `.env`，并执行数据库 schema/seed。数据库密码只在首次配置时隐藏输入，永远不写入仓库。

## 日常使用

```powershell
.\scripts\start-local.ps1
```

该命令会幂等地：检查或启动 SSH 隧道 `localhost:15432 -> 115.159.67.119:127.0.0.1:5432`、启动 FastAPI `127.0.0.1:8000`、启动 Next.js `localhost:3000`，然后执行健康检查。

常用变体：

- `.\scripts\start-local.ps1 -ApiOnly`：只启动隧道和 API。
- `.\scripts\start-local.ps1 -NoSeed`：跳过重复 seed，只启动服务。
- `.\scripts\check-local.ps1`：查看 15432/8000/3000 监听状态并执行真实 smoke query。
- `.\scripts\stop-local.ps1`：停止本地 API、前端和 SSH 隧道。

## 安全约束

- `.env`、数据库口令和私钥均在 `.gitignore` 中或仓库之外；提交前运行 `git status --short` 检查。
- 不要把 `DATABASE_URL` 改为云服务器公网地址；它应继续指向 `127.0.0.1:15432`。
- 不要为 PostgreSQL 打开公网 5432。未来云端部署时，应用容器应加入 1Panel PostgreSQL 所在 Docker network，并由 HTTPS 反向代理暴露 Web/API。
