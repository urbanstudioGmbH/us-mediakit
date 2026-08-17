"""SQLAlchemy-Modelle: `ApiKey`, `UsageEvent`.

`UsageEvent` ist **append-only** (GoBD-Anforderung an die Grundaufzeichnung, siehe
Programmierplan Abschnitt 4): nach dem Schreiben nie per `UPDATE`/`DELETE` verändern.
Löschroutinen dürfen ausschließlich `duration_ms` betreffen (operative Zusatzfelder,
12 Monate Aufbewahrung), nicht `bytes_in`/`bytes_out`/`credits`/`operation`/
`account_ref`/`occurred_at` (abrechnungsrelevanter Kern, 8 Jahre Aufbewahrung — fachlich
vom Steuerberater zu bestätigen, siehe Abschnitt 9).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(primary_key=True)
    account_ref: Mapped[str] = mapped_column(index=True)
    key_prefix: Mapped[str]
    key_hash: Mapped[str]  # SHA-256, der Klartext-Key wird nie gespeichert
    label: Mapped[str]
    status: Mapped[str] = mapped_column(default="active")  # "active" | "suspended"
    created_at: Mapped[datetime]
    last_used_at: Mapped[datetime | None] = mapped_column(default=None)


class UsageEvent(Base):
    __tablename__ = "usage_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(unique=True, index=True)  # = Idempotenz-Key
    api_key_id: Mapped[str] = mapped_column(index=True)
    account_ref: Mapped[str] = mapped_column(index=True)  # denormalisiert
    operation: Mapped[str]
    # "thumbnail" | "meta.read" | "meta.write" | "c2pa.sign" | "c2pa.verify" | "video"
    # | "pdf" | "ai_upscale" | "caption" | "watermark_visible" | "watermark_invisible"
    # | "watermark_detect"
    provider: Mapped[str | None]  # z. B. "real-esrgan", "seedvr2-3b", "claid-ai"
    status: Mapped[str]  # "ok" | "error"
    occurred_at: Mapped[datetime] = mapped_column(index=True)
    bytes_in: Mapped[int]
    bytes_out: Mapped[int]
    credits: Mapped[float]
    credits_table_version: Mapped[int]
    external_cost_micros: Mapped[int | None]  # nur bei ai_upscale (claid-ai) gefüllt
    duration_ms: Mapped[int]

    __table_args__ = (Index("ix_usage_events_account_occurred", "account_ref", "occurred_at"),)
