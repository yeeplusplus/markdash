from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    markets: Mapped[list[Market]] = relationship(back_populates="event")


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    event_id: Mapped[str | None] = mapped_column(Text, ForeignKey("events.id"))
    side_label: Mapped[str | None] = mapped_column(Text)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcomes: Mapped[list] = mapped_column(JSONB, nullable=False)
    volume: Mapped[float | None] = mapped_column(Numeric)
    liquidity: Mapped[float | None] = mapped_column(Numeric)
    active: Mapped[bool | None] = mapped_column(Boolean)
    closed: Mapped[bool | None] = mapped_column(Boolean)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    event: Mapped[Event | None] = relationship(back_populates="markets")
    snapshots: Mapped[list[MarketSnapshot]] = relationship(back_populates="market")

    __table_args__ = (Index("idx_markets_event", "event_id"),)


class MarketSnapshot(Base):
    __tablename__ = "market_snapshots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    market_id: Mapped[str] = mapped_column(Text, ForeignKey("markets.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    yes_price: Mapped[float | None] = mapped_column(Numeric)
    prices: Mapped[dict] = mapped_column(JSONB, nullable=False)
    volume: Mapped[float | None] = mapped_column(Numeric)
    liquidity: Mapped[float | None] = mapped_column(Numeric)

    market: Mapped[Market] = relationship(back_populates="snapshots")

    __table_args__ = (Index("idx_snapshots_market_ts", "market_id", "ts"),)


class AIInsight(Base):
    __tablename__ = "ai_insights"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    event_id: Mapped[str | None] = mapped_column(Text, ForeignKey("events.id"))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_bucket: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stddev: Mapped[float | None] = mapped_column(Numeric)
    arb_gap: Mapped[float | None] = mapped_column(Numeric)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_insights_kind_created", "kind", "created_at"),
        UniqueConstraint("kind", "event_id", "window_bucket", name="uq_insights_kind_event_bucket"),
    )
