"""Persistence via SQLAlchemy.

DATABASE_URL set   -> that database (MySQL: mysql+pymysql://user:pass@host:3306/agrisentry). The database is
                      created if missing, tables are created, and missing columns are ADDED (never dropped).
DATABASE_URL empty -> in-memory SQLite: same code path, but nothing survives a restart ("demo, not persisted").
Image binaries are stored on disk (config.UPLOAD_DIR); the database stores references only.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, create_engine, inspect,
                        select, text)
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import StaticPool
from . import config


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # stored as naive UTC


def iso(dt: datetime | None) -> str | None:
    return dt.replace(tzinfo=timezone.utc).isoformat() if dt else None


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
    is_seed: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=utcnow)


class WeatherObservation(Base):
    __tablename__ = "weather_observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int | None] = mapped_column(ForeignKey("farms.id"), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(20))
    observed_at: Mapped[datetime] = mapped_column(DateTime)
    temp_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    rh: Mapped[float | None] = mapped_column(Float, nullable=True)
    rain_mm: Mapped[float | None] = mapped_column(Float, nullable=True)


class RiskAssessment(Base):  # kept from the MVP schema for compatibility
    __tablename__ = "risk_assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int | None] = mapped_column(ForeignKey("farms.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    data_mode: Mapped[str] = mapped_column(String(30))
    index_value: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String(20))
    factors: Mapped[dict] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)


class ImagePrediction(Base):
    __tablename__ = "image_predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int | None] = mapped_column(ForeignKey("farms.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    label: Mapped[str] = mapped_column(String(100))
    score: Mapped[float] = mapped_column(Float)
    latency_ms: Mapped[float] = mapped_column(Float)
    filename: Mapped[str | None] = mapped_column(String(200), nullable=True)
    crop: Mapped[str | None] = mapped_column(String(40), nullable=True)
    image_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Assessment(Base):
    """One saved, combined assessment (what the History page shows)."""
    __tablename__ = "assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    farm_id: Mapped[int | None] = mapped_column(ForeignKey("farms.id"), nullable=True, index=True)
    location_label: Mapped[str] = mapped_column(String(200))
    crop: Mapped[str] = mapped_column(String(40))
    data_mode: Mapped[str] = mapped_column(String(20))  # live | normal | conducive
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    predicted_label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    image_uncertain: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    image_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    risk_status: Mapped[str] = mapped_column(String(20))
    risk_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    advisory_level: Mapped[str] = mapped_column(String(20))
    advisory_headline: Mapped[str] = mapped_column(String(200))
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    farm_id: Mapped[int | None] = mapped_column(ForeignKey("farms.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    level: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    kind: Mapped[str | None] = mapped_column(String(20), nullable=True)            # weather | image
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_key: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    location_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    simulated: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    acknowledged: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


_engine = None
_error: str | None = None
_persistent = False


def _ensure_mysql_database(url) -> None:
    if url.get_backend_name() != "mysql" or not url.database:
        return
    server = create_engine(url.set(database=None), pool_pre_ping=True)
    with server.connect() as c:
        c.execute(text(f"CREATE DATABASE IF NOT EXISTS `{url.database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
    server.dispose()


def _migrate(engine) -> list[str]:
    """Additive-only migration: add columns that exist in the models but not in the database."""
    added = []
    insp = inspect(engine)
    with engine.begin() as c:
        for table in Base.metadata.sorted_tables:
            if not insp.has_table(table.name):
                continue
            have = {col["name"] for col in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in have:
                    ddl = col.type.compile(dialect=engine.dialect)
                    c.execute(text(f"ALTER TABLE {table.name} ADD COLUMN {col.name} {ddl} NULL"))
                    added.append(f"{table.name}.{col.name}")
    return added


def init(url: str | None = None) -> None:
    global _engine, _error, _persistent
    url = config.DATABASE_URL if url is None else url
    _error = None
    try:
        if url:
            u = make_url(url)
            _ensure_mysql_database(u)
            engine = create_engine(u, pool_pre_ping=True, pool_recycle=1800)
            _persistent = True
        else:
            engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
            _persistent = False
        _migrate(engine)
        Base.metadata.create_all(engine)
        with Session(engine) as s:
            if not s.scalar(select(Farm.id).limit(1)):
                for f in config.FARMS:
                    s.add(Farm(**f, is_seed=True))
                s.commit()
        _engine = engine
    except Exception as e:
        _engine, _persistent = None, False
        _error = f"{type(e).__name__}: {str(e).splitlines()[0][:200]}"
        if url:  # keep the app usable: fall back to labelled in-memory storage
            init("")
            _error = f"Could not use DATABASE_URL ({_error}); running in-memory, nothing is saved."


def status() -> dict:
    mode = "persistent" if _persistent else "demo (in-memory, not persisted)"
    backend = _engine.dialect.name if _engine is not None else None
    return {"configured": bool(config.DATABASE_URL), "connected": _engine is not None, "persistent": _persistent,
            "backend": backend, "mode": mode, "error": _error}


def session() -> Session:
    if _engine is None:
        init()
    return Session(_engine)


# ---------- farms ----------
def farm_dict(f: Farm) -> dict:
    return {"id": f.id, "name": f.name, "location": f.location, "lat": f.lat, "lon": f.lon, "crop": f.crop,
            "is_seed": bool(f.is_seed)}


def list_farms() -> list[dict]:
    with session() as s:
        return [farm_dict(f) for f in s.scalars(select(Farm).order_by(Farm.id))]


def get_farm(farm_id: int) -> dict | None:
    with session() as s:
        f = s.get(Farm, farm_id)
        return farm_dict(f) if f else None


def create_farm(name: str, location: str, lat: float, lon: float, crop: str) -> dict:
    with session() as s:
        f = Farm(name=name, location=location, lat=lat, lon=lon, crop=crop, is_seed=False)
        s.add(f)
        s.commit()
        return farm_dict(f)


def delete_farm(farm_id: int) -> bool:
    with session() as s:
        f = s.get(Farm, farm_id)
        if not f:
            return False
        for model in (Assessment, Alert, ImagePrediction, WeatherObservation, RiskAssessment):  # keep history, drop link
            for row in s.scalars(select(model).where(model.farm_id == farm_id)):
                row.farm_id = None
        s.delete(f)
        s.commit()
        return True


# ---------- image predictions ----------
def save_image(farm_id: int | None, res: dict, filename: str | None, image_ref: str | None) -> None:
    if res.get("status") != "ok":
        return
    with session() as s:
        s.add(ImagePrediction(farm_id=farm_id, label=res["label"], score=res["score"], latency_ms=res["latency_ms"],
                              filename=(filename or "")[:200], crop=res.get("selected_crop"), image_ref=image_ref,
                              model_version=res.get("model_version")))
        s.commit()


# ---------- assessments ----------
def save_assessment(*, farm_id, location_label, crop, mode, weather, risk, image, advisory) -> dict:
    img_ok = bool(image and image.get("status") == "ok")
    with session() as s:
        cur = (weather or {}).get("current")
        if cur and weather.get("status") == "live":
            s.add(WeatherObservation(farm_id=farm_id, mode="live", observed_at=cur["time"].astimezone(timezone.utc).replace(tzinfo=None),
                                     temp_c=cur.get("temp_c"), rh=cur.get("rh"), rain_mm=cur.get("rain_mm")))
        a = Assessment(
            farm_id=farm_id, location_label=location_label[:200], crop=crop, data_mode=mode, simulated=mode != "live",
            predicted_label=image["label"] if img_ok else None, confidence=image["score"] if img_ok else None,
            image_uncertain=image.get("uncertain") if img_ok else None, image_ref=(image or {}).get("image_ref"),
            risk_status=risk.get("status", "unavailable"), risk_index=risk.get("index"), risk_category=risk.get("category"),
            advisory_level=advisory["level"], advisory_headline=advisory["headline"][:200],
            recommendation=" ".join(advisory["inspect"][:2] + advisory["actions"][:2]),
            model_version=image.get("model_version") if img_ok else None)
        s.add(a)
        s.commit()
        return assessment_dict(a)


def assessment_dict(a: Assessment) -> dict:
    return {c.name: getattr(a, c.name) for c in Assessment.__table__.columns} | {"created_at": iso(a.created_at)}


def list_assessments(farm_id: int | None = None, limit: int = 50) -> list[dict]:
    with session() as s:
        q = select(Assessment).order_by(Assessment.created_at.desc(), Assessment.id.desc()).limit(limit)
        if farm_id:
            q = q.where(Assessment.farm_id == farm_id)
        return [assessment_dict(a) for a in s.scalars(q)]


# ---------- alerts ----------
RANK = {"Low": 0, "Moderate": 1, "High": 2, "Very High": 3}
REPEAT_AFTER = timedelta(hours=24)


def alert_dict(a: Alert) -> dict:
    return {"id": a.id, "farm_id": a.farm_id, "created_at": iso(a.created_at), "level": a.level, "message": a.message,
            "kind": a.kind, "explanation": a.explanation, "location_label": a.location_label, "category": a.category,
            "simulated": bool(a.simulated), "acknowledged": bool(a.acknowledged), "acknowledged_at": iso(a.acknowledged_at)}


def evaluate_weather_alert(*, location_key: str, location_label: str, farm_id, risk: dict, simulated: bool) -> dict | None:
    """Create an alert when late-blight favourability is (or is forecast within 48 h to be) High+.

    Duplicate suppression: no new alert while the latest alert for this location and data source has the
    same or a higher category and is less than 24 h old. A rise in category always alerts.
    """
    if risk.get("status") != "ok":
        return None
    p48 = risk.get("peak_48h")
    now_cat = risk["category"]
    cat = p48["category"] if p48 and RANK[p48["category"]] > RANK[now_cat] else now_cat
    if RANK[cat] < RANK["High"]:
        return None
    with session() as s:
        last = s.scalars(select(Alert).where(Alert.location_key == location_key, Alert.kind == "weather",
                                             Alert.simulated == simulated).order_by(Alert.created_at.desc(), Alert.id.desc()).limit(1)).first()
        if last and RANK.get(last.category or "", -1) >= RANK[cat] and utcnow() - last.created_at < REPEAT_AFTER:
            return None
        forecast = cat != now_cat
        msg = (f"Late-blight favourability forecast to reach {cat} within 48 h" if forecast
               else f"Late-blight favourability is {cat} now")
        expl = risk["explanation"]
        a = Alert(farm_id=farm_id, level="alert" if cat == "Very High" else "warning", message=f"{msg} – {location_label}",
                  kind="weather", explanation=expl, location_key=location_key, location_label=location_label, category=cat,
                  simulated=simulated, acknowledged=False)
        s.add(a)
        s.commit()
        return alert_dict(a)


def image_alert(*, farm_id, location_label: str, advisory: dict, image: dict) -> dict | None:
    """Alert for a saved assessment whose image shows a confident disease prediction."""
    if not image or image.get("status") != "ok" or image.get("healthy") or image.get("uncertain"):
        return None
    with session() as s:
        a = Alert(farm_id=farm_id, level=advisory["level"] if advisory["level"] in ("warning", "alert") else "warning",
                  message=f"{advisory['headline']} – {location_label}", kind="image",
                  explanation=f"Image screening: {image['crop']} – {image['condition']} (model score {image['score']:.0%}). Verify in the field.",
                  location_key=None, location_label=location_label, category=None, simulated=False, acknowledged=False)
        s.add(a)
        s.commit()
        return alert_dict(a)


def list_alerts(include_acknowledged: bool = True, limit: int = 100) -> list[dict]:
    with session() as s:
        q = select(Alert).order_by(Alert.created_at.desc(), Alert.id.desc()).limit(limit)
        if not include_acknowledged:
            q = q.where((Alert.acknowledged == False) | (Alert.acknowledged.is_(None)))  # noqa: E712
        return [alert_dict(a) for a in s.scalars(q)]


def acknowledge_alert(alert_id: int) -> dict | None:
    with session() as s:
        a = s.get(Alert, alert_id)
        if not a:
            return None
        if not a.acknowledged:
            a.acknowledged, a.acknowledged_at = True, utcnow()
            s.commit()
        return alert_dict(a)
