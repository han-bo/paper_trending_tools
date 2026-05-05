# GitHub + arXiv Intelligence Agent（个人版 MVP）

个人研究情报系统：自动抓取 GitHub 与 arXiv，规则层排序，可选火山引擎 LLM 深度分析；每日摘要可通过 **Telegram** 和/或 **邮件**（标准库 `smtplib`，无额外依赖）推送。

## 环境

- Python 3.10+

## 安装

```bash
cd /path/to/paper_trending_tools
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入令牌与密钥
```

## 配置说明

- `GITHUB_TOKEN`：GitHub PAT，提高 REST API 限额并访问私有数据以外的高级能力（**强烈建议配置**）。
- `VOLCENGINE_API_KEY` / `VOLCENGINE_MODEL`：火山方舟 OpenAI 兼容接口的 API Key 与接入点 ID（`ep-...`）。未配置时将只做规则层评分。
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`：BotFather 创建的 Bot 与目标会话 ID。未配置则跳过 Telegram。
- **邮件**：配置 `SMTP_HOST`、`SMTP_FROM`、`DIGEST_EMAIL_TO`（多个收件人用英文逗号分隔）后即会发送与 Telegram 相同正文的纯文本邮件。常用项：`SMTP_PORT`（默认 `587`）、`SMTP_USER` / `SMTP_PASSWORD`、`SMTP_STARTTLS`（默认 `true`）。若使用 **465 + SSL**，设 `SMTP_PORT=465`、`SMTP_USE_SSL=true`、`SMTP_STARTTLS=false`。可选 `DIGEST_EMAIL_SUBJECT` 自定义主题。

## 运行

立即执行一次全流程：

```bash
python -m app.main --once
```

按 `.env` 中的 Cron 配置常驻调度（默认每天 8:00，时区 `Asia/Shanghai`）：

```bash
python -m app.main
```

## 使用与排错说明

### GitHub 速率限制

未配置或无效 `GITHUB_TOKEN` 时，GitHub REST API 的**匿名额度很低**，一次任务会对多个仓库分别请求 contributors、releases、commits、README 等，很容易触发 **403 rate limit**，日志里会出现 `API rate limit exceeded`。此时大量仓库详情会拉取失败，当日 GitHub 侧结果可能偏空。

**请务必在 `.env` 中配置有效的 `GITHUB_TOKEN`**，以保证每日流程稳定可用。

### LLM 与推送渠道（Telegram / 邮件）可选

- 未配置 `VOLCENGINE_API_KEY` / `VOLCENGINE_MODEL` 时，会**跳过 LLM**，仅使用规则层评分；数据库仍会写入本轮抓取记录。
- **Telegram** 与 **邮件**可同时开启，也可只开其一。若两者均未配置，仍会生成摘要并写入 `daily_digest` 表，此时 `sent_status` 为 `skipped`；否则 `sent_status` 会记录各渠道结果（例如 `email:sent`、`telegram:sent` 或 `email:error:…`）。

### 搜索与「趋势」偏好

默认 `GITHUB_SEARCH_QUERY` 偏「高星 + 近期有推送」，若你更关注**新库或某一类主题**，可在 `.env` 中调整 `GITHUB_SEARCH_QUERY`（例如收紧 `stars` 区间或增加关键词），并可配合 `GITHUB_PUSHED_DAYS`、`GITHUB_PER_PAGE` 控制范围与列表长度。

### 摘要与数据库

- 每日推送格式与规划一致：GitHub Top N、arXiv Top M、「今天最值得深入研究的是：…」（N/M 由 `DIGEST_GITHUB_TOP_N`、`DIGEST_ARXIV_TOP_N` 配置）。
- SQLite 默认路径为项目下 `data/local.db`（可通过 `DATABASE_URL` 修改）；`data/local.db` 已加入 `.gitignore`，请勿将含密钥或隐私的 `.env` 提交到版本库。

## 项目结构

与规划文档一致：`app/crawler`、`app/ranking`、`app/llm`、`app/notifier`、`app/db`、`app/scheduler`、`prompts/`、`data/`（含 `local.db` 运行时生成）、`.env`、`requirements.txt`、本说明。

## Git 远程（本仓库）

已配置的默认远程 `origin`（SSH）为：

```text
ssh://root@static.alex-tech.org:22/~/git/paper_trend.git
```

首次在本机关联远程（若尚未添加）：

```bash
git remote add origin ssh://root@static.alex-tech.org:22/~/git/paper_trend.git
git push -u origin main
```

### 若 `git push` 被拒绝

说明远端 `main` 上**已有其他提交**（例如现有博客仓库历史）。当前本仓库与远端**无共同祖先**时，Git 会拒绝非快进推送。

请任选其一（务必先确认不会误删远端需要保留的内容）：

1. **专用裸库（推荐）**：在服务器上新建空裸库（例如 `~/git/paper_trending_tools.git`），将 `origin` 改为新地址再 `git push -u origin main`。
2. **确认覆盖该远程地址**：仅当你确定要用本项目**完全替换**远端 `paper_trend.git` 当前内容时，再执行  
   `git push --force-with-lease origin main`（会改写远端 `main` 历史）。

推送前需本机已能 `ssh` 登录 `root@static.alex-tech.org`，且远端路径为可写的 Git 仓库。
