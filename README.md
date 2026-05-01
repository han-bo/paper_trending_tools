# GitHub + arXiv Intelligence Agent（个人版 MVP）

个人研究情报系统：自动抓取 GitHub 与 arXiv，规则层排序，可选火山引擎 LLM 深度分析，并通过 Telegram 推送每日摘要。

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
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`：BotFather 创建的 Bot 与目标会话 ID。未配置时仍会写入 `daily_digest` 表，但不推送。

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

### LLM 与 Telegram 可选

- 未配置 `VOLCENGINE_API_KEY` / `VOLCENGINE_MODEL` 时，会**跳过 LLM**，仅使用规则层评分；数据库仍会写入本轮抓取记录。
- 未配置 `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` 时，会**跳过 Telegram 推送**，仍会生成摘要正文并写入 `daily_digest` 表（`sent_status` 一般为 `skipped`）。

### 搜索与「趋势」偏好

默认 `GITHUB_SEARCH_QUERY` 偏「高星 + 近期有推送」，若你更关注**新库或某一类主题**，可在 `.env` 中调整 `GITHUB_SEARCH_QUERY`（例如收紧 `stars` 区间或增加关键词），并可配合 `GITHUB_PUSHED_DAYS`、`GITHUB_PER_PAGE` 控制范围与列表长度。

### 摘要与数据库

- 每日推送格式与规划一致：GitHub Top N、arXiv Top M、「今天最值得深入研究的是：…」（N/M 由 `DIGEST_GITHUB_TOP_N`、`DIGEST_ARXIV_TOP_N` 配置）。
- SQLite 默认路径为项目下 `data/local.db`（可通过 `DATABASE_URL` 修改）；`data/local.db` 已加入 `.gitignore`，请勿将含密钥或隐私的 `.env` 提交到版本库。

## 项目结构

与规划文档一致：`app/crawler`、`app/ranking`、`app/llm`、`app/notifier`、`app/db`、`app/scheduler`、`prompts/`、`data/`（含 `local.db` 运行时生成）、`.env`、`requirements.txt`、本说明。

## Git 远程（本仓库）

本地仓库可推送至单独远程（SSH）：

```text
ssh://root@static.alex-tech.org:22/~/git/blog.git
```

首次推送示例（需本机已配置对该主机的 SSH 访问，且远端已创建空仓库）：

```bash
git remote add origin ssh://root@static.alex-tech.org:22/~/git/blog.git
git push -u origin main
```
