# 运维笔记 — A股全量信息检索知识库 (pm-a-stock-kb)

> 本文档为运维人员提供 on-call、监控、回滚、应急响应和常用 SQL 查询索引。
> 与 `RUNBOOK.md`（部署手册）配合使用，本文档侧重 **运行时运维**。

---

## 1. On-Call 值班指南

### 1.1 服务概览

| 项目 | 值 |
|------|-----|
| 仓库 | `D:/workspace/projects/pm-a-stock-kb/` |
| GitHub | `https://github.com/ttmens/pm-a-stock-kb` |
| Pages | `https://ttmens.github.io/pm-a-stock-kb/` |
| 技术栈 | FastAPI + SQLite (FTS5) + 单页前端 (HTML/CSS/JS) |
| 端口 | 8000 (默认，可通过 `$PORT` 修改) |
| Python | 3.11+ |
| 数据库 | `04-mvp/data/astock_kb.db` (SQLite, WAL 模式) |

### 1.2 关键端点

| 端点 | 方法 | 认证 | 用途 |
|------|------|------|------|
| `/api/health` | GET | 公开 | 健康检查 |
| `/api/stocks?q=` | GET | 公开 | 股票搜索 |
| `/api/events/{code}` | GET | Bearer Token | 事件链查询 |
| `/api/search?q=` | GET | Bearer Token | 全文搜索 (FTS5) |
| `/api/factors` | GET | Bearer Token | 因子数据 + CSV 导出 |
| `/api/schedule` | GET/POST | Bearer Token | ETL 任务调度 |

### 1.3 启动/停止/重启

```bash
# 启动 (MVP 推荐)
cd D:/workspace/projects/pm-a-stock-kb/04-mvp
export API_TOKEN="your-token"
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1

# 后台启动
nohup uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1 > server.log 2>&1 &
echo $! > server.pid

# 停止
kill $(cat server.pid) 2>/dev/null || pkill -f "uvicorn api.main"

# 重启
kill $(cat server.pid) 2>/dev/null
sleep 2
nohup uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 1 > server.log 2>&1 &
echo $! > server.pid
```

### 1.4 环境变量

| 变量 | 默认值 | 必填 | 说明 |
|------|--------|------|------|
| `API_TOKEN` | `demo-token-123` | 是 | API 认证 Token (Bearer) |
| `HOST` | `0.0.0.0` | 否 | 监听地址 |
| `PORT` | `8000` | 否 | 监听端口 |
| `DB_PATH` | (自动) | 否 | SQLite 数据库路径 |

### 1.5 依赖安装

```bash
cd D:/workspace/projects/pm-a-stock-kb
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r 04-mvp/api/requirements.txt
```

依赖: fastapi>=0.115.0, uvicorn>=0.32.0, pydantic>=2.0, aiosqlite>=0.20.0, pytest>=8.0, httpx>=0.27.0

---

## 2. 监控

### 2.1 健康检查

```bash
# 基础健康检查
curl -s http://localhost:8000/api/health | python -m json.tool

# 预期响应
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

> **注意:** `components` 中显示 `unhealthy` 在 MVP 阶段是正常的（使用 SQLite/FTS5 替代 PG/ES），这是架构演进中的预期行为。

### 2.2 关键性能指标

| 指标 | 阈值 | 说明 |
|------|------|------|
| 全文搜索 P95 延迟 | <100ms | FTS5 索引查询 |
| 事件链查询响应 | <200ms | SQLite 索引查询 |
| 内存使用 | <85% | 72 小时稳定运行 |
| 数据库大小 | <500MB (沪深 300) | 含 FTS 索引 |

### 2.3 日志

| 日志类型 | 位置 | 说明 |
|----------|------|------|
| 服务日志 | `server.log` (uvicorn 输出) | 启动、请求、错误日志 |
| 访问日志 | uvicorn 默认 stdout | 生产建议接入 structured logging |
| 测试输出 | `pytest tests/ -v` | 42 个测试用例 |

### 2.4 监控脚本 (可选)

```bash
#!/bin/bash
# 简单监控循环 — 每 30 秒检查一次
while true; do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health)
  TIME=$(date '+%Y-%m-%d %H:%M:%S')
  if [ "$STATUS" != "200" ]; then
    echo "[$TIME] HEALTH CHECK FAILED: HTTP $STATUS"
    # 可在此添加告警逻辑 (邮件/钉钉/微信)
  else
    echo "[$TIME] OK"
  fi
  sleep 30
done
```

### 2.5 数据库完整性检查

```bash
cd D:/workspace/projects/pm-a-stock-kb/04-mvp
python -c "
import sqlite3
conn = sqlite3.connect('data/astock_kb.db')
c = conn.cursor()
c.execute('PRAGMA integrity_check')
print('Integrity:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM stocks')
print('Stocks:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM events')
print('Events:', c.fetchone()[0])
c.execute('SELECT COUNT(*) FROM factor_values')
print('Factors:', c.fetchone()[0])
conn.close()
"
```

---

## 3. 回滚方案

### 3.1 回滚触发条件

| 条件 | 动作 |
|------|------|
| 服务启动失败 | 检查 Python 版本、依赖安装 |
| 健康检查持续失败 | 检查数据库文件权限 |
| 前端白屏 | 检查 `04-mvp/web/index.html` 完整性 |
| 数据库损坏 | 从备份恢复 `.db` 文件 |
| 新版本引入回归 | git checkout 到上一个稳定 commit |

### 3.2 回滚步骤

```bash
# 1. 停止当前服务
kill $(cat server.pid) 2>/dev/null || pkill -f "uvicorn api.main"

# 2. 回滚代码 (如果部署了新版本)
cd D:/workspace/projects/pm-a-stock-kb
git log --oneline -5        # 查看最近 5 个 commit
git checkout <previous-commit>

# 3. 恢复数据库 (如果有备份)
cp 04-mvp/data/astock_kb.db.bak 04-mvp/data/astock_kb.db

# 4. 重新启动
cd 04-mvp
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### 3.3 数据库备份策略

```bash
# 手动备份
cp 04-mvp/data/astock_kb.db 04-mvp/data/astock_kb.db.$(date +%Y%m%d_%H%M%S)

# 恢复指定备份
cp 04-mvp/data/astock_kb.db.YYYYMMDD_HHMMSS 04-mvp/data/astock_kb.db

# 定时备份 (cron, 每天凌晨 2 点)
# 0 2 * * * cp /opt/astock-kb/04-mvp/data/astock_kb.db /opt/astock-kb/04-mvp/data/astock_kb.db.$(date +\%Y\%m\%d)
```

### 3.4 Git 回滚

```bash
# 查看当前版本
git log --oneline -10

# 回退到指定 commit
git checkout <commit-sha>

# 或者回退上一个 commit
git revert HEAD

# 确认回滚后重新启动服务
cd 04-mvp
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

---

## 4. 应急响应 (Incident Response)

### 4.1 事件分级

| 级别 | 描述 | 响应时间 | 示例 |
|------|------|----------|------|
| P0 - 紧急 | 服务完全不可用 | 立即 | 进程崩溃、数据库损坏、端口冲突 |
| P1 - 高 | 核心功能异常 | 30 分钟内 | API 返回 500、搜索无结果 |
| P2 - 中 | 非核心功能异常 | 2 小时内 | 因子导出慢、前端样式异常 |
| P3 - 低 | 轻微问题 | 下次维护窗口 | 日志格式不规范、拼写错误 |

### 4.2 P0 应急响应: 服务完全不可用

**症状:** `curl http://localhost:8000/api/health` 超时或连接拒绝

**排查步骤:**

```bash
# 1. 检查进程是否在运行
ps aux | grep uvicorn

# 2. 检查端口是否被占用
netstat -tlnp | grep 8000    # Linux
# 或
lsof -i :8000

# 3. 检查日志
tail -100 server.log

# 4. 检查 Python 环境
python --version
pip list | grep -E "fastapi|uvicorn"

# 5. 检查数据库文件
ls -la 04-mvp/data/astock_kb.db
file 04-mvp/data/astock_kb.db

# 6. 尝试手动启动
cd 04-mvp
python -c "from api.db import init_db; init_db(); print('DB OK')"
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**恢复方案:**

1. 如果进程崩溃 → 重启服务 (见 1.3 节)
2. 如果数据库损坏 → 从备份恢复 (见 3.3 节)
3. 如果端口冲突 → 修改 `PORT` 环境变量或释放占用端口
4. 如果依赖缺失 → `pip install -r 04-mvp/api/requirements.txt`

### 4.3 P1 应急响应: API 返回 500 错误

**症状:** 健康检查返回 200，但业务端点返回 500

**排查步骤:**

```bash
# 1. 确认错误范围
curl -v http://localhost:8000/api/stocks?q=茅台           # 公开端点
curl -v -H "Authorization: Bearer $API_TOKEN" http://localhost:8000/api/events/600519.SH

# 2. 检查认证
curl -v http://localhost:8000/api/events/600519.SH        # 应该返回 401
curl -v -H "Authorization: Bearer wrong-token" http://localhost:8000/api/events/600519.SH  # 应该返回 403

# 3. 检查数据库查询
python -c "
import sqlite3
conn = sqlite3.connect('04-mvp/data/astock_kb.db')
print('Stocks:', conn.execute('SELECT COUNT(*) FROM stocks').fetchone()[0])
print('Events:', conn.execute('SELECT COUNT(*) FROM events').fetchone()[0])
print('FTS:', conn.execute('SELECT COUNT(*) FROM events_fts').fetchone()[0])
conn.close()
"

# 4. 检查服务日志中的 traceback
grep -i "traceback\|error\|exception" server.log | tail -20
```

### 4.4 P2 应急响应: 搜索响应缓慢

**症状:** 全文搜索响应 > 500ms (阈值 100ms)

**排查步骤:**

```bash
# 1. 测量搜索延迟
curl -w "\nTime: %{time_total}s\n" -H "Authorization: Bearer $API_TOKEN" \
  "http://localhost:8000/api/search?q=芯片"

# 2. 检查数据库大小
du -h 04-mvp/data/astock_kb.db

# 3. 检查 FTS 索引完整性
python -c "
import sqlite3
conn = sqlite3.connect('04-mvp/data/astock_kb.db')
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM events')
events = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM events_fts')
fts = c.fetchone()[0]
print(f'Events: {events}, FTS entries: {fts}')
if events != fts:
    print('WARNING: FTS index out of sync!')
    c.execute('INSERT INTO events_fts(events_fts) VALUES(\"rebuild\")')
    conn.commit()
    print('FTS index rebuilt.')
conn.close()
"
```

### 4.5 安全事件响应

**API Token 泄露:**

```bash
# 1. 立即更换 Token
export API_TOKEN="new-secure-token-$(openssl rand -hex 16)"

# 2. 重启服务使新 Token 生效
kill $(cat server.pid) 2>/dev/null
cd 04-mvp
uvicorn api.main:app --host 0.0.0.0 --port 8000

# 3. 更新所有客户端的 Token
# 通知使用者更新 Bearer Token
```

**数据库文件泄露:**

```bash
# 1. 限制文件权限
chmod 600 04-mvp/data/astock_kb.db

# 2. 检查文件所有者
ls -la 04-mvp/data/astock_kb.db

# 3. 如有必要，迁移数据库到安全目录
mkdir -p /opt/astock-kb/data
mv 04-mvp/data/astock_kb.db /opt/astock-kb/data/
export DB_PATH=/opt/astock-kb/data/astock_kb.db
```

---

## 5. SQL / 查询索引

### 5.1 数据库 Schema

数据库路径: `04-mvp/data/astock_kb.db`
模式: SQLite 3 + FTS5 全文索引 + WAL 日志模式

**表结构:**

| 表名 | 用途 | 行数 (种子) |
|------|------|-------------|
| `stocks` | 股票元数据 | 10 |
| `events` | 事件数据 | 41 |
| `factor_values` | 因子数据 (sentiment/momentum/volatility) | 390 |
| `etl_tasks` | ETL 调度任务 | 0 |
| `events_fts` | FTS5 全文索引 (虚拟表) | 41 |

### 5.2 常用查询

#### 股票查询

```sql
-- 查询所有股票
SELECT stock_code, stock_name, industry FROM stocks ORDER BY stock_code;

-- 按行业筛选
SELECT stock_code, stock_name FROM stocks WHERE industry = '白酒';

-- 模糊搜索股票名称
SELECT stock_code, stock_name FROM stocks WHERE stock_name LIKE '%茅台%';

-- 查询股票详情
SELECT * FROM stocks WHERE stock_code = '600519.SH';
```

#### 事件查询

```sql
-- 查询某股票的事件链 (按时间倒序)
SELECT e.event_id, e.event_type, e.event_time, e.title, e.source, e.sentiment_score, s.stock_name
FROM events e
JOIN stocks s ON e.stock_code = s.stock_code
WHERE e.stock_code = '600519.SH'
ORDER BY e.event_time DESC;

-- 查询某股票近 N 天的事件
SELECT * FROM events
WHERE stock_code = '600519.SH'
  AND event_time >= datetime('now', '-30 days')
ORDER BY event_time DESC;

-- 按事件类型筛选
SELECT * FROM events
WHERE stock_code = '600519.SH' AND event_type = 'announcement'
ORDER BY event_time DESC;

-- 查询情感评分最高的事件 (TOP 10)
SELECT stock_code, title, sentiment_score FROM events
ORDER BY sentiment_score DESC LIMIT 10;

-- 按事件类型统计
SELECT event_type, COUNT(*) as cnt FROM events GROUP BY event_type ORDER BY cnt DESC;

-- 按来源统计
SELECT source, COUNT(*) as cnt FROM events GROUP BY source ORDER BY cnt DESC;
```

#### 全文搜索 (FTS5)

```sql
-- 全文搜索关键词
SELECT e.event_id, e.title, e.event_type, e.stock_code, e.sentiment_score,
       highlight(events_fts, 0, '[', ']') as highlighted_title,
       highlight(events_fts, 1, '[', ']') as highlighted_content
FROM events_fts
WHERE events_fts MATCH '芯片'
ORDER BY rank;

-- 多关键词搜索 (AND)
SELECT * FROM events_fts WHERE events_fts MATCH '芯片 AND 制裁';

-- 按股票代码过滤的全文搜索
SELECT e.* FROM events e
INNER JOIN events_fts f ON e.event_id = f.rowid
WHERE f MATCH '茅台' AND e.stock_code = '600519.SH';

-- 按事件类型过滤的全文搜索
SELECT e.* FROM events e
INNER JOIN events_fts f ON e.event_id = f.rowid
WHERE f MATCH '业绩' AND e.event_type = 'financial';

-- 重建 FTS 索引 (数据不同步时)
INSERT INTO events_fts(events_fts) VALUES('rebuild');
```

#### 因子数据查询

```sql
-- 查询某股票的因子数据
SELECT factor_date, factor_name, factor_value FROM factor_values
WHERE stock_code = '600519.SH'
ORDER BY factor_date DESC;

-- 查询特定因子 (如 sentiment)
SELECT stock_code, factor_date, factor_value FROM factor_values
WHERE factor_name = 'sentiment' AND stock_code = '600519.SH'
ORDER BY factor_date DESC;

-- 查询最新因子数据
SELECT stock_code, factor_name, factor_value, factor_date FROM factor_values f1
WHERE factor_date = (SELECT MAX(factor_date) FROM factor_values f2 WHERE f2.stock_code = f1.stock_code AND f2.factor_name = f1.factor_name)
ORDER BY stock_code, factor_name;

-- 因子趋势分析 (某股票 sentiment 趋势)
SELECT factor_date, factor_value FROM factor_values
WHERE stock_code = '600519.SH' AND factor_name = 'sentiment'
ORDER BY factor_date;

-- 全市场因子统计
SELECT factor_name,
       AVG(factor_value) as avg_val,
       MIN(factor_value) as min_val,
       MAX(factor_value) as max_val,
       COUNT(*) as cnt
FROM factor_values
GROUP BY factor_name;
```

#### ETL 任务管理

```sql
-- 查看所有 ETL 任务
SELECT * FROM etl_tasks ORDER BY created_at DESC;

-- 查看运行中的任务
SELECT * FROM etl_tasks WHERE status = 'running';

-- 查看失败的任务
SELECT * FROM etl_tasks WHERE status = 'failed' ORDER BY created_at DESC;

-- 统计各状态任务数量
SELECT status, COUNT(*) as cnt FROM etl_tasks GROUP BY status;
```

#### 数据库维护

```sql
-- 检查数据库完整性
PRAGMA integrity_check;

-- 检查 WAL 模式
PRAGMA journal_mode;

-- 检查外键约束
PRAGMA foreign_key_check;

-- 数据库大小分析 (SQLite 3.17+)
SELECT name, pgsize * (pgcnt - 1) as size
FROM dbstat
GROUP BY name
ORDER BY size DESC;

-- 查看索引大小
SELECT name, pgsize * pgcnt as size_bytes
FROM dbstat
WHERE name LIKE 'idx_%'
ORDER BY size_bytes DESC;
```

### 5.3 命令行快速查询

```bash
# 使用 sqlite3 命令行
sqlite3 04-mvp/data/astock_kb.db "SELECT COUNT(*) FROM stocks;"

# 导出为 CSV
sqlite3 -header -csv 04-mvp/data/astock_kb.db \
  "SELECT stock_code, stock_name, industry FROM stocks;" > stocks.csv

# 交互式查询
sqlite3 04-mvp/data/astock_kb.db
sqlite> .mode column
sqlite> .headers on
sqlite> SELECT * FROM stocks LIMIT 5;
sqlite> .quit
```

---

## 6. 已知限制 (MVP)

| 限制 | 说明 | 后续计划 |
|------|------|----------|
| 单用户 | 无多用户/权限管理 | v2 添加用户系统 |
| 数据覆盖 | 仅沪深 300 (10 只种子) | ETL 管道扩展至全市场 |
| 情感因子 | 预计算种子数据 | 接入本地 LLM 实时生成 |
| ETL 调度 | 仅手动触发 | 添加 cron 定时任务 |
| 组件健康 | PG/ES/Redis 显示 unhealthy | MVP 使用 SQLite 替代 |
| Token 存储 | 前端 localStorage | 生产建议 Cookie httpOnly |
| CORS | `allow_origins=["*"]` | 生产环境应限制域名 |

---

## 7. 上线前检查清单 (快速参考)

- [ ] 所有测试通过 (`cd 04-mvp && pytest tests/ -v` → 42/42)
- [ ] UI 验收通过 (101/100, G3 门禁)
- [ ] 环境变量 `API_TOKEN` 已配置 (非默认值)
- [ ] 数据库初始化完成 (种子数据就绪)
- [ ] 数据库备份策略已配置
- [ ] 健康检查端点可访问
- [ ] 前端 5 个屏幕加载正常
- [ ] 回滚方案已验证

---

*文档生成时间: 2026-06-12*
*对应 Commit: 8b594b9*
*Pages: https://ttmens.github.io/pm-a-stock-kb/*
