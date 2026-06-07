from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class GitHubProject(Base):
    __tablename__ = "github_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repo_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    repo_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    stars_growth: Mapped[int] = mapped_column(Integer, default=0)
    contributors: Mapped[int] = mapped_column(Integer, default=0)
    last_commit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issue_count: Mapped[int] = mapped_column(Integer, default=0)
    release_count: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str | None] = mapped_column(String(128), nullable=True)
    topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_readme: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    ai_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    worth_follow: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now().astimezone(),
    )


class ArxivPaper(Base):
    __tablename__ = "arxiv_papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(1024), nullable=False)
    authors: Mapped[str | None] = mapped_column(Text, nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    paper_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    pdf_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    category: Mapped[str | None] = mapped_column(String(512), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    github_repo_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    ai_rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    worth_follow: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now().astimezone(),
    )


class UserFeedback(Base):
    __tablename__ = "user_feedback"
    __table_args__ = (
        UniqueConstraint("item_type", "item_key", "digest_date", name="uq_feedback_item_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    item_key: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    digest_date: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    signal: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now().astimezone(),
    )


class DailyDigest(Base):
    __tablename__ = "daily_digest"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sent_status: Mapped[str] = mapped_column(String(64), default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now().astimezone(),
    )
