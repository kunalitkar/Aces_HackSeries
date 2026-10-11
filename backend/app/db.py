"""Optional persistence. Enabled only when DATABASE_URL is set (MySQL: mysql+pymysql://...)."""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship
from . import config


def _now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Farm(Base):
    __tablename__ = "farms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    location: Mapped[str] = mapped_column(String(160))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    crop: Mapped[str] = mapped_column(String(40), default="Tomato")


class WeatherObservation(Base):
    __tablename__ = "weather_observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), index=True)
    mode: Mapped[str] = mapped_column(String(20))  # live | demo
    observed_at: Mapped[datetime] = mapped_column(DateTime)
    temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    rh: Mapped[float | None] = mapped_column(Float, nullable=True)
    rain_mm: Mapped[float | None] = mapped_column(Float, nullable=True)


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    data_mode: Mapped[str] = mapped_column(String(30))
    index_value: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(20))
    factors: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)


class ImagePrediction(Base):
    __tablename__ = "image_predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int | None] = mapped_column(ForeignKey("farms.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    label: Mapped[str] = mapped_column(String(100))
    score: Mapped[float] = mapped_column(Float)
    latency_ms: Mapped[float] = mapped_column(Float)
    filename: Mapped[str | None] = mapped_column(String(200), nullable=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    level: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)


_engine = None
_error: str | None = None


def init() -> None:
    global _engine, _error
    if not config.DATABASE_URL:
        return
    try:
        _engine = create_engine(config.DATABASE_URL, pool_pre_ping=True)
        Base.metadata.create_all(_engine)
        with Session(_engine) as s:
            for f in config.FARMS:
                if not s.get(Farm, f["id"]):
                    s.add(Farm(**{k: f[k] for k in ("id", "name", "location", "lat", "lon", "crop")}))
            s.commit()
    except Exception as e:
        _engine, _error = None, f"{type(e).__name__}: {e}"


def status() -> dict:
    if not config.DATABASE_URL:
        return {"configured": False, "connected": False, "mode": "demo (no persistence)"}
    return {"configured": True, "connected": _engine is not None, "error": _error,
            "mode": "persistent" if _engine else "unavailable"}


def enabled() -> bool:
    return _engine is not None


def save_assessment(farm_id: int, mode: str, risk: dict, current: dict | None, level: str, headline: str) -> None:
    if not enabled():
        return
    with Session(_engine) as s:
        if current:
            s.add(WeatherObservation(farm_id=farm_id, mode="demo" if mode != "live" else "live",
                                     observed_at=current["time"].replace(tzinfo=None), temp_c=current.get("temp_c"),
                                     rh=current.get("rh"), rain_mm=current.get("rain_mm")))
        s.add(RiskAssessment(farm_id=farm_id, data_mode=mode, index_value=risk["index"], category=risk["category"],
                             factors={"factors": risk["factors"]}, explanation=risk["explanation"]))
        if level in ("warning", "alert"):
            s.add(Alert(farm_id=farm_id, level=level, message=headline))
        s.commit()


def save_image(farm_id: int | None, res: dict, filename: str | None) -> None:
    if not enabled() or res.get("status") != "ok":
        return
    with Session(_engine) as s:
        s.add(ImagePrediction(farm_id=farm_id, label=res["label"], score=res["score"],
                              latency_ms=res["latency_ms"], filename=(filename or "")[:200]))
        s.commit()


def history(farm_id: int | None, limit: int = 30) -> list[dict]:
    if not enabled():
        return []
    rows: list[dict] = []
    with Session(_engine) as s:
        q = select(RiskAssessment).order_by(RiskAssessment.created_at.desc()).limit(limit)
        if farm_id:
            q = q.where(RiskAssessment.farm_id == farm_id)
        for r in s.scalars(q):
            rows.append({"id": f"risk-{r.id}", "type": "risk", "farm_id": r.farm_id, "created_at": r.created_at.isoformat() + "Z",
                         "title": f"Weather favourability {r.index_value:.0f}/100 ({r.category})",
                         "detail": r.explanation, "data_mode": r.data_mode, "synthetic": r.data_mode in ("normal", "conducive")})
        q2 = select(ImagePrediction).order_by(ImagePrediction.created_at.desc()).limit(limit)
        if farm_id:
            q2 = q2.where(ImagePrediction.farm_id == farm_id)
        for r in s.scalars(q2):
            rows.append({"id": f"img-{r.id}", "type": "image", "farm_id": r.farm_id, "created_at": r.created_at.isoformat() + "Z",
                         "title": f"Leaf image: {r.label.replace('___', ' – ').replace('_', ' ')}",
                         "detail": f"Model softmax score {r.score:.0%}; {r.latency_ms:.0f} ms", "data_mode": "image", "synthetic": False})
    return sorted(rows, key=lambda r: r["created_at"], reverse=True)[:limit]
