# 部署运行手册 — A股全量信息检索知识库 (pm-a-stock-kb)

## 项目概况

| 项目 | 值 |
|------|-----|
| 仓库 | `D:/workspace/projects/pm-a-stock-kb/` |
| GitHub | `https://github.com/ttmens/pm-a-stock-kb` |
| Pages | `https://ttmens.github.io/pm-a-stock-kb/` |
| 技术栈 | FastAPI + SQLite (FTS5) + 单页前端 (HTML/CSS/JS) |
| 端口 | 8000 (默认) |
| Python | 3.11+ |

## 架构

```
┌─────────────────────────────────────────┐
│  前端: 04-mvp/web/index.html (SPA)       │
│  - 5个屏幕 + 1个详情弹窗                  │
│  - 零外部依赖，内联CSS/JS                 │
└──────────────┬──────────────────────────┘
               │ fetch API
               ▼
┌─────────────────────────────────────────┐
│  FastAPI (04-mvp/api/)                   │
│  ├─ /api/stocks    股票搜索              │
│  ├─ /api/events    事件链查询            │
│  ├─ /api/search    全文搜索 (FTS5)       │
│  ├─ /api/factors   因子数据 + CSV导出    │
│  ├─ /api/health    健康检查              │
│  └─ /api/schedule  ETL任务调度           │
└──────────────┬──────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────┐
│  SQLite: 04-mvp/data/astock_kb.db        │
│  - stocks, events, factor_values,        │
│    etl_tasks 表                          │
│  - events_fts 全文索引                    │
└─────────────────────────────────────────┘
```

## 环境变量

| 变量 | 默认值 | 必填 | 说明 |
|------|--------|------|------|
| `API_TOKEN` | `demo-token-123` | 是 | API 认证 Token (Bearer) |
| `HOST` | `0.0.0.0` | 否 | 监听地址 |
| `PORT` | `8000` | 否 | 监听端口 |
| `DB_PATH` | (自动) | 否 | SQLite 数据库路径 (默认: `04-mvp/data/astock_kb.db`) |

### .env 示例

```
API_TOKEN=your-secret-token-here
PORT=8000
HOST=0.0.0.0
```

## 部署步骤

### 前置条件

- Python 3.11+
- Linux / WSL / Windows 均可运行
- 推荐: 16GB RAM (含后续 ETL + 本地 LLM)
- MVP 阶段仅需 Python + SQLite

### Step 1: 准备环境

```bash
# 进入项目目录
cd /d/workspace/projects/pm-a-stock-kb

# 创建虚拟环境 (推荐)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r 04-mvp/api/requirements.txt
```

### Step 2: 配置环境变量

```bash
# 设置 API Token (生产环境务必修改!)
export API_TOKEN="your-secure-token-here"
export PORT=8000
export HOST=0.0.0.0
```

### Step 3: 初始化数据库 (首次部署)

```bash
cd 04-mvp
python -c "from api.db import init_db; init_db(); print('DB initialized')"
```

数据库将自动创建在 `04-mvp/data/astock_kb.db`，包含:
- 10 只沪深300种子股票
- 41 条种子事件
- 390 条种子因子数据
- FTS5 全文索引

### Step 4: 启动服务

```bash
cd 04-mvp
uvicorn api.main:app --host $HOST --port $PORT --workers 1
```

或使用 `python`:
```bash
cd 04-mvp
python -c "import uvicorn; uvicorn.run('api.main:app', host='0.0.0.0', port=8000)"
```

### Step 5: 验证部署

```bash
# 健康检查 (公开端点，无需Token)
curl http://localhost:8000/api/health

# 股票搜索 (GET公开)
curl "http://localhost:8000/api/stocks?q=茅台"

# 事件链 (需要Token)
curl -H "Authorization: Bearer $API_TOKEN" \
  "http://localhost:8000/api/events/600519.SH?days=30"

# 全文搜索 (需要Token)
curl -H "Authorization: Bearer $API_TOKEN" \
  "http://localhost:8000/api/search?q=芯片&page=1"

# 前端访问
# 浏览器打开: http://localhost:8000/
# 或在浏览器中直接打开: 04-mvp/web/index.html (离线模式)
```

### Step 6: 运行测试

```bash
cd 04-mvp
pytest tests/ -v
```

预期: 42 个测试全部通过 (含认证、事件链、全文搜索、因子、健康检查)

## 生产部署选项

### 选项 A: 直接 uvicorn (推荐 MVP)

```bash
nohup uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1 > server.log 2>&1 &
echo $! > server.pid
```

### 选项 B: systemd 服务

创建 `/etc/systemd/system/astock-kb.service`:

```ini
[Unit]
Description=A股全量信息检索知识库
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/astock-kb/04-mvp
Environment=API_TOKEN=your-token
ExecStart=/opt/astock-kb/.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable astock-kb
sudo systemctl start astock-kb
sudo systemctl status astock-kb
```

### 选项 C: Docker (未来 ETL + LLM 阶段)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY 04-mvp/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY 04-mvp/ .
EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 运行后验证

| 检查项 | 命令 | 预期结果 |
|--------|------|----------|
| 健康检查 | `curl http://localhost:8000/api/health` | HTTP 200, components 状态 |
| 认证拦截 | `curl http://localhost:8000/api/events/600519.SH` | HTTP 401 |
| Token 通过 | `curl -H "Authorization: Bearer $API_TOKEN" http://localhost:8000/api/events/600519.SH` | HTTP 200 + 事件列表 |
| 全文搜索 | `curl -H "Authorization: Bearer $API_TOKEN" "http://localhost:8000/api/search?q=芯片"` | HTTP 200 + 搜索结果 |
| 前端加载 | 浏览器访问 `http://localhost:8000/` | 5个导航标签正常显示 |
| 事件链 | 前端点击贵州茅台 → 事件链 | 时间线展示正常 |
| 因子导出 | 前端因子页 → 导出CSV | 下载CSV文件 |

## 监控

### 日志

- 服务日志: `server.log` (uvicorn 输出)
- 访问日志: uvicorn 默认输出 (生产建议接入 structured logging)

### 关键指标

| 指标 | 阈值 | 说明 |
|------|------|------|
| 全文搜索 P95 延迟 | <100ms | FTS5 索引查询 |
| 事件链查询响应 | <200ms | SQLite 索引查询 |
| 内存使用 | <85% | 72小时稳定运行 |
| 数据库大小 | <500MB (沪深300) | 含 FTS 索引 |

### 健康检查端点

`GET /api/health` 返回:
```json
{
  "status": "healthy",
  "uptime_seconds": 12345,
  "memory_mb": 45.2,
  "data_freshness": "T+1",
  "components": {
    "postgresql": {"status": "unhealthy", "note": "MVP使用SQLite"},
    "elasticsearch": {"status": "unhealthy", "note": "MVP使用FTS5"},
    "redis": {"status": "unhealthy", "note": "MVP无需缓存"},
    "llm": {"status": "unhealthy", "note": "MVP使用预计算情感因子"}
  }
}
```

> **注意:** MVP 阶段 components 显示 unhealthy 是正常的 (使用 SQLite/FTS5 替代 PG/ES)，这是架构演进中的预期行为。

## 回滚方案

### 回滚触发条件

| 条件 | 动作 |
|------|------|
| 服务启动失败 | 检查 Python 版本、依赖安装 |
| 健康检查持续失败 | 检查数据库文件权限 |
| 前端白屏 | 检查 `04-mvp/web/index.html` 完整性 |
| 数据库损坏 | 从备份恢复 `.db` 文件 |

### 回滚步骤

```bash
# 1. 停止当前服务
kill $(cat server.pid) 2>/dev/null || pkill -f "uvicorn api.main"

# 2. 恢复代码 (如果部署了新版本)
git checkout <previous-commit>

# 3. 恢复数据库 (如果有备份)
cp data/astock_kb.db.bak data/astock_kb.db

# 4. 重新启动
cd 04-mvp
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### 数据库备份

```bash
# 备份
cp 04-mvp/data/astock_kb.db 04-mvp/data/astock_kb.db.$(date +%Y%m%d)

# 恢复
cp 04-mvp/data/astock_kb.db.YYYYMMDD 04-mvp/data/astock_kb.db
```

## 安全注意事项

1. **API_TOKEN**: 生产环境务必修改默认值 `demo-token-123`
2. **CORS**: 当前配置 `allow_origins=["*"]`，生产环境应限制域名
3. **Token 存储**: 前端 Token 存储在 localStorage，MVP 阶段可接受，生产建议 Cookie httpOnly
4. **数据库**: SQLite 文件权限应限制为应用用户读写
5. **输入验证**: FastAPI Query 参数已有基本验证 (days: 1-365)

## 上线前检查清单 (Deploy Checklist)

### Pre-Deploy
- [x] 所有测试通过 (42/42 pytest)
- [x] UI 验收通过 (101/100, G3 门禁)
- [x] RUNBOOK.md 部署文档就绪
- [x] 环境变量 API_TOKEN 已配置
- [x] 数据库初始化 (种子数据就绪)
- [x] 回滚方案文档化

### Deploy
- [ ] 启动 uvicorn 服务
- [ ] 运行冒烟测试 (curl 健康检查 + API 调用)
- [ ] 验证前端 5 个屏幕加载正常
- [ ] 监控内存和响应时间 15 分钟

### Post-Deploy
- [ ] 确认关键用户流程 (搜索 → 事件链 → 因子导出)
- [ ] 更新 release notes
- [ ] 通知使用者

### 回滚触发条件
- 服务启动失败且 3 次重试无效
- 健康检查持续返回 500
- 前端白屏或 API 全部 500
- 数据库文件损坏

## 已知限制 (MVP)

| 限制 | 说明 | 后续计划 |
|------|------|----------|
| 单用户 | 无多用户/权限管理 | v2 添加用户系统 |
| 数据覆盖 | 仅沪深300 (10只种子) | ETL 管道扩展至全市场 |
| 情感因子 | 预计算种子数据 | 接入本地 LLM 实时生成 |
| ETL 调度 | 仅手动触发 | 添加 cron 定时任务 |
| 组件健康 | PG/ES/Redis 显示 unhealthy | MVP 使用 SQLite 替代 |
