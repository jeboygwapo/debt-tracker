from datetime import date, datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa.text("false"))
    email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True, unique=True, index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa.text("false"))
    verify_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    verify_token_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    income_config: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    debts: Mapped[list["Debt"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    monthly_entries: Mapped[list["MonthlyEntry"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    ai_cache: Mapped[Optional["AiCache"]] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)


class Debt(Base):
    __tablename__ = "debts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(32), default="credit_card")  # credit_card | loan
    apr_monthly_pct: Mapped[float] = mapped_column(Float, default=0.0)
    note: Mapped[Optional[str]] = mapped_column(Text)

    # fixed payment fields (replaces fixed_payments config)
    is_fixed: Mapped[bool] = mapped_column(Boolean, default=False)
    fixed_monthly: Mapped[Optional[float]] = mapped_column(Float)
    fixed_ends: Mapped[Optional[str]] = mapped_column(String(7))        # YYYY-MM
    fixed_reduced_monthly: Mapped[Optional[float]] = mapped_column(Float)
    fixed_reduced_threshold: Mapped[Optional[float]] = mapped_column(Float)
    allow_prepayment: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sa.text('false'))

    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="debts")
    monthly_entries: Mapped[list["MonthlyEntry"]] = relationship(back_populates="debt", cascade="all, delete-orphan")


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    monthly_sar: Mapped[float] = mapped_column(Float, default=0.0, server_default=sa.text("0"))
    ends: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=sa.text("0"))


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(32), default="bank", server_default=sa.text("'bank'"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=sa.text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    snapshots: Mapped[list["AccountSnapshot"]] = relationship(back_populates="account", cascade="all, delete-orphan")


class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    month: Mapped[str] = mapped_column(String(7), index=True)
    balance: Mapped[float] = mapped_column(Float, default=0.0, server_default=sa.text("0"))
    source: Mapped[str] = mapped_column(String(16), default="manual", server_default=sa.text("'manual'"))
    statement_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    account: Mapped["Account"] = relationship(back_populates="snapshots")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    target_php: Mapped[float] = mapped_column(Float, default=0.0, server_default=sa.text("0"))
    current_php: Mapped[float] = mapped_column(Float, default=0.0, server_default=sa.text("0"))
    target_date: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    monthly_alloc_php: Mapped[float] = mapped_column(Float, default=0.0, server_default=sa.text("0"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default=sa.text("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MonthlyEntry(Base):
    __tablename__ = "monthly_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    debt_id: Mapped[int] = mapped_column(ForeignKey("debts.id", ondelete="CASCADE"), nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # YYYY-MM

    balance: Mapped[float] = mapped_column(Float, default=0.0)
    min_due: Mapped[float] = mapped_column(Float, default=0.0)
    payment: Mapped[float] = mapped_column(Float, default=0.0)
    paid_on: Mapped[Optional[str]] = mapped_column(String(32))
    due_date: Mapped[Optional[str]] = mapped_column(String(32))
    note: Mapped[Optional[str]] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="monthly_entries")
    debt: Mapped["Debt"] = relationship(back_populates="monthly_entries")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    reads: Mapped[list["NotificationRead"]] = relationship(back_populates="notification", cascade="all, delete-orphan")
    creator: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by])


class NotificationRead(Base):
    __tablename__ = "notification_reads"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    notification_id: Mapped[int] = mapped_column(ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False, index=True)
    read_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    notification: Mapped["Notification"] = relationship(back_populates="reads")


class AiCache(Base):
    __tablename__ = "ai_cache"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    data_hash: Mapped[str] = mapped_column(String(32))
    html: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[date] = mapped_column(Date)
    daily_count: Mapped[int] = mapped_column(default=0)

    user: Mapped["User"] = relationship(back_populates="ai_cache")
