# 反馈 Harness 改动说明与部署清单

> 日期：2026-06-07  
> 范围：邮件 L1 反馈（👍/👎）、降权重排、周报、反馈 HTTP 服务

---

## 一、今天改了什么

### 1.1 功能概述

在原有「抓取 → 规则分 → LLM → 推送」流水线上，增加了 **价值 harness 闭环**：

1. 邮件 digest 每条下方有 **👍 值得 / 👎 不满意** 链接（HTML 按钮）
2. 点击链接 → 公网 HTTPS → 反馈服务 → 写入 SQLite → 静态确认页
3. 历史 👎 对排序 **降权**（-5 分/次，上限 -20）
4. **每周一 9:00**（可配置）自动生成反馈周报，经 APScheduler 发邮件（无需 crontab）
5. Telegram digest 仍为纯文本，**不含**反馈链接

### 1.2 新增文件

| 路径 | 说明 |
|------|------|
| `app/feedback/__init__.py` | 反馈模块包 |
| `app/feedback/keys.py` | 稳定 item_key（`owner/repo`、`2301.12345`） |
| `app/feedback/links.py` | HMAC 签名反馈链接生成与校验 |
| `app/feedback/penalty.py` | 👎 降权计算与 penalty map |
| `app/feedback/storage.py` | 反馈落库（同条目同天可覆盖） |
| `app/feedback/digest.py` | 结构化 digest、HTML/纯文本渲染 |
| `app/feedback/server.py` | 轻量 HTTP 反馈服务（stdlib） |
| `app/feedback/report.py` | 周报生成 |
| `app/feedback/static/confirm.html` | 点击后「感谢反馈」确认页 |
| `paper-trending-feedback.service` | 反馈服务 systemd 单元 |
| `docs/feedback-harness-deploy.md` | 本文档 |

### 1.3 修改文件

| 路径 | 改动要点 |
|------|----------|
| `app/db/models.py` | 新增 `UserFeedback` 表；`GitHubProject` / `ArxivPaper` 增加 `ai_rating` 字段 |
| `app/db/session.py` | 启动时 SQLite 自动迁移，为旧库补 `ai_rating` 列 |
| `app/config.py` | 新增 `FEEDBACK_*`、`FEEDBACK_REPORT_*` 配置项 |
| `app/scheduler/jobs.py` | 降权排序、结构化 digest、HTML 邮件、LLM 结果写 `ai_rating`、APScheduler 周报 job |
| `app/notifier/email_notify.py` | 支持 HTML 邮件；新增 `send_report_email` |
| `app/notifier/zoho_mail.py` | `mailFormat` 支持 `html` |
| `app/main.py` | 新增 CLI：`--run-feedback-server`、`--feedback-report`、`--email-report` |
| `.env.example` | 补充反馈与周报相关环境变量说明 |

### 1.4 数据模型

**新表 `user_feedback`**

| 字段 | 说明 |
|------|------|
| `item_type` | `github` / `arxiv` |
| `item_key` | 稳定键，如 `some-org/repo` 或 `2301.12345` |
| `digest_date` | 摘要日期 `YYYY-MM-DD` |
| `signal` | `up` / `down` |
| `created_at` | 点击时间 |

唯一约束：`(item_type, item_key, digest_date)` — 同一天对同一条目只保留最新意见。

**降权规则**

```text
effective_score = base_score - min(20, down_count × 5)
```

- 👍 只统计，不加分
- 作用于 digest Top-N 排序与「今日建议」

### 1.5 新增 CLI

```bash
# 启动反馈 HTTP 服务（供 nginx 反代）
python -m app.main --run-feedback-server

# 手动查看近 7 天周报
python -m app.main --feedback-report

# 手动发邮件周报
python -m app.main --feedback-report --email-report

# 指定统计天数
python -m app.main --feedback-report --feedback-days 14
```

### 1.6 调度方式（无需 crontab）

| Job | 触发 | 进程 |
|-----|------|------|
| 每日 digest | `SCHEDULER_CRON_HOUR` / `MINUTE` | `paper-trending.service` |
| 每周反馈周报 | `FEEDBACK_REPORT_DOW` 等 | 同上，APScheduler 第二 job |

反馈 HTTP 服务是 **独立进程**：`paper-trending-feedback.service`。

---

## 二、架构与部署位置

```text
Cloudflare DNS:  fb.yourdomain.com  →  VPS 公网 IP
                                      ↓
VPS nginx :443  ──反代──→  127.0.0.1:8081  (paper-trending-feedback)
                                      ↓
                              SQLite data/local.db
                                      ↑
VPS paper-trending.service  ──────────┘  (抓取/LLM/发信/周报)
```

| 组件 | 部署在哪 | 是否需公网 |
|------|----------|------------|
| 代码 + venv + `.env` | VPS | 否 |
| SQLite `data/local.db` | VPS | 否 |
| `paper-trending.service` | VPS systemd | 否（主动出站） |
| `paper-trending-feedback.service` | VPS systemd，`127.0.0.1:8081` | 不直接暴露 |
| nginx + HTTPS | VPS | 是（443） |
| Cloudflare DNS | Cloudflare 控制台 | — |
| Zoho / GitHub / arXiv / 火山方舟 | 外部 SaaS | 不用部署 |

**只需要一个反馈子域**（如 `fb.yourdomain.com`），不必动主域名或博客。

---

## 三、待办：VPS 本机

假设项目路径为 `/root/workdir/paper_trending`（与现有 systemd 一致）。

### 3.1 更新代码与依赖

```bash
cd /root/workdir/paper_trending
git pull
source .venv/bin/activate
pip install -r requirements.txt
```

### 3.2 配置 `.env`

在现有配置基础上 **追加**（域名换成你的）：

```env
FEEDBACK_BASE_URL=https://fb.yourdomain.com
FEEDBACK_HMAC_SECRET=<openssl rand -hex 32>

FEEDBACK_PENALTY_PER_DOWN=5
FEEDBACK_PENALTY_CAP=20

FEEDBACK_LISTEN_HOST=127.0.0.1
FEEDBACK_LISTEN_PORT=8081

FEEDBACK_REPORT_DOW=mon
FEEDBACK_REPORT_HOUR=9
FEEDBACK_REPORT_MINUTE=0
FEEDBACK_REPORT_DAYS=7
FEEDBACK_REPORT_EMAIL=true
```

生成 secret 示例：

```bash
openssl rand -hex 32
```

**注意**：`FEEDBACK_BASE_URL` 必须与 Cloudflare/nginx 上的子域 **完全一致**（含 `https://`）。

### 3.3 启用 systemd 服务

```bash
sudo cp paper-trending.service /etc/systemd/system/
sudo cp paper-trending-feedback.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now paper-trending
sudo systemctl enable --now paper-trending-feedback
```

检查：

```bash
sudo systemctl status paper-trending paper-trending-feedback
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8081/f/up
# 期望 404（无参数），说明服务在监听
```

改 `.env` 后需重启：

```bash
sudo systemctl restart paper-trending paper-trending-feedback
```

### 3.4 配置 nginx

新建 `/etc/nginx/sites-available/paper-trending-feedback`：

```nginx
server {
    listen 80;
    server_name fb.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8081;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用：

```bash
sudo ln -s /etc/nginx/sites-available/paper-trending-feedback /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

HTTPS 二选一：

- **Cloudflare Origin Certificate** + nginx `listen 443 ssl`（橙云代理时推荐）
- **Let's Encrypt (certbot)**（必要时将 `fb` 记录临时设为 DNS only 再签证书）

Cloudflare SSL 模式建议：**Full** 或 **Full (strict)**。

### 3.5 防火墙

```bash
sudo ufw allow 22
sudo ufw allow 80
sudo ufw allow 443
# 不要开放 8081
```

---

## 四、待办：Cloudflare

在 Cloudflare → 你的域名 → **DNS** → **Records** 新增：

| 类型 | 名称 | 内容 | 代理 |
|------|------|------|------|
| A | `fb` | VPS 公网 IP | Proxied（推荐）或 DNS only |

示例：`fb.yourdomain.com` → `123.456.789.0`

主域名 `@` / `www` **无需**为本项目改动。

---

## 五、验证清单

按顺序执行：

- [ ] Cloudflare：`fb` A 记录指向 VPS IP
- [ ] VPS：`paper-trending`、`paper-trending-feedback` 均为 `active (running)`
- [ ] 本机：`curl -I http://127.0.0.1:8081/f/up` 有 HTTP 响应
- [ ] 公网：`curl -I https://fb.yourdomain.com/f/up` HTTPS 正常
- [ ] `.env` 中 `FEEDBACK_BASE_URL` 与 DNS 一致
- [ ] 跑一轮：`python -m app.main --once`，收到 HTML 邮件
- [ ] 点击邮件中 👍 或 👎，出现「感谢反馈」确认页
- [ ] 数据库有记录（或 `--feedback-report` 能看到统计）
- [ ] 可选：`python -m app.main --feedback-report` 手动看周报

---

## 六、日常使用

| 场景 | 做法 |
|------|------|
| 收每日 digest | 自动，无需操作 |
| 对条目反馈 | 点邮件里 👍/👎 |
| 看周报 | 每周一自动发邮件；或手动 `--feedback-report` |
| 临时跑一轮 | `python -m app.main --once` |
| 看库 | `python -m app.main --inspect-db` |

---

## 七、常见问题

| 现象 | 可能原因 |
|------|----------|
| 邮件无 👍/👎 按钮 | 未配 `FEEDBACK_BASE_URL` / `FEEDBACK_HMAC_SECRET` |
| 链接 403 | `FEEDBACK_HMAC_SECRET` 与生成链接时不一致 |
| 链接打不开 | `paper-trending-feedback` 未启动，或 nginx/DNS 未配 |
| 点了没进库 | 反馈服务连的不是同一个 `data/local.db`（检查 `DATABASE_URL`） |
| 降权没生效 | 需等下次 `--once` / 每日 pipeline 跑完；降权按 **item_key 历史累计 👎** |
| 周报没收到 | 检查 `FEEDBACK_REPORT_EMAIL=true` 且 Zoho / `DIGEST_EMAIL_TO` 已配 |

---

## 八、尚未实现（后续可选）

- Telegram digest 反馈按钮
- 邮件 multipart（HTML + plain 同一封）
- 离线 golden set / prompt 回归评估
- 👎 时间衰减、按主题/语言降权
- Web 面板浏览历史与反馈统计
