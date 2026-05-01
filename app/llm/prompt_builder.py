from __future__ import annotations

import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent


def load_template(filename: str) -> str:
    path = _ROOT / "prompts" / filename
    return path.read_text(encoding="utf-8")


def build_github_prompt(
    *,
    repo_name: str,
    description: str,
    readme: str,
    stars: int,
    contributors: int,
    recent_activity: str,
) -> str:
    tpl = load_template("github_analysis.txt")
    return tpl.format(
        repo_name=repo_name,
        description=description or "（无）",
        readme=(readme or "（无 README）")[:12000],
        stars=stars,
        contributors=contributors,
        recent_activity=recent_activity or "（无）",
    )


def build_paper_prompt(
    *,
    title: str,
    abstract: str,
    authors: str,
    category: str,
    github_repo: str,
) -> str:
    tpl = load_template("paper_analysis.txt")
    return tpl.format(
        title=title,
        abstract=abstract or "（无）",
        authors=authors or "（无）",
        category=category or "（无）",
        github_repo=github_repo or "未发现明显 GitHub 仓库链接",
    )


def parse_final_score_1_to_10(text: str) -> float | None:
    """从模型输出中解析「1~10 分」的最终评分。"""
    if not text:
        return None
    patterns = [
        r"最终(?:给出)?\s*[：:]?\s*(\d+(?:\.\d+)?)\s*分",
        r"(?:评分|分数)\s*[：:]\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*/\s*10",
    ]
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            try:
                v = float(m.group(1))
                if 1.0 <= v <= 10.0:
                    return v
                if 0.0 <= v <= 1.0:
                    return v * 10.0
            except ValueError:
                continue
    m = re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)(?=\s*分)", text)
    if m:
        try:
            v = float(m[-1])
            if 1.0 <= v <= 10.0:
                return v
        except ValueError:
            pass
    return None
