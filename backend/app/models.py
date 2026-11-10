"""数据表定义。字段含义见方案文档第 3 节「核心数据对象」与 4.8 节。"""
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.db import Base
from app.services.clock import TZ


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """统一按 UTC 存、读出来一定带时区。不带时区的输入当作北京时间。SQLite 和 PostgreSQL 行为一致。"""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=TZ)
        value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    openid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    unionid: Mapped[str | None] = mapped_column(String(64))
    nickname: Mapped[str | None] = mapped_column(String(64))
    avatar_url: Mapped[str | None] = mapped_column(String(512))
    gender: Mapped[str | None] = mapped_column(String(8))  # male / female
    birthday: Mapped[date | None] = mapped_column(Date)
    height_cm: Mapped[float | None] = mapped_column(Float)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    # 健康数据、病历用药属于敏感个人信息，需单独授权
    health_consent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    medical_consent_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)


class Subscription(Base):
    """会员状态的唯一依据。到期后按 free 计算，无需定时任务改表。"""

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    tier: Mapped[str] = mapped_column(String(8))  # pro / max
    start_at: Mapped[datetime] = mapped_column(UTCDateTime())
    end_at: Mapped[datetime] = mapped_column(UTCDateTime())


class RedeemCode(TimestampMixin, Base):
    __tablename__ = "redeem_codes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    tier: Mapped[str] = mapped_column(String(8))
    days: Mapped[int] = mapped_column(Integer)
    batch: Mapped[str | None] = mapped_column(String(64))
    redeem_before: Mapped[date | None] = mapped_column(Date)
    used_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class MembershipLog(TimestampMixin, Base):
    __tablename__ = "membership_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(16))  # trial / code / admin
    tier: Mapped[str] = mapped_column(String(8))
    days: Mapped[int] = mapped_column(Integer)
    code: Mapped[str | None] = mapped_column(String(32))
    end_at: Mapped[datetime] = mapped_column(UTCDateTime())
    note: Mapped[str | None] = mapped_column(String(200))


class Upload(TimestampMixin, Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # food / inbody / medicine / medical / routine / avatar
    key: Mapped[str] = mapped_column(String(256), unique=True)
    content_type: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)


class BodyRecord(TimestampMixin, Base):
    __tablename__ = "body_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    measured_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    source: Mapped[str] = mapped_column(String(16))  # inbody / manual / weight
    weight_kg: Mapped[float | None] = mapped_column(Float)
    bmi: Mapped[float | None] = mapped_column(Float)
    body_fat_pct: Mapped[float | None] = mapped_column(Float)
    body_fat_kg: Mapped[float | None] = mapped_column(Float)
    fat_free_mass_kg: Mapped[float | None] = mapped_column(Float)
    skeletal_muscle_kg: Mapped[float | None] = mapped_column(Float)
    visceral_fat_level: Mapped[float | None] = mapped_column(Float)
    bmr_kcal: Mapped[float | None] = mapped_column(Float)
    body_water_kg: Mapped[float | None] = mapped_column(Float)
    protein_kg: Mapped[float | None] = mapped_column(Float)
    mineral_kg: Mapped[float | None] = mapped_column(Float)
    inbody_score: Mapped[float | None] = mapped_column(Float)
    segments: Mapped[dict | None] = mapped_column(JSON)  # 五节段肌肉/脂肪
    confidence: Mapped[dict | None] = mapped_column(JSON)
    image_upload_id: Mapped[int | None] = mapped_column(ForeignKey("uploads.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(String(500))


class Food(Base):
    """食物库：每 100g 营养素 + 自己的生活量词。"""

    __tablename__ = "foods"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    category: Mapped[str] = mapped_column(String(16))
    kcal: Mapped[float] = mapped_column(Float)
    carb: Mapped[float] = mapped_column(Float)
    protein: Mapped[float] = mapped_column(Float)
    fat: Mapped[float] = mapped_column(Float)
    unit_name: Mapped[str] = mapped_column(String(8))  # 只 / 碗 / 个 / 盘
    unit_grams: Mapped[float] = mapped_column(Float)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    verified: Mapped[bool] = mapped_column(Boolean, default=True)  # 模型自估补进来的为 False，待审


class MealLog(TimestampMixin, Base):
    __tablename__ = "meal_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    meal_type: Mapped[str] = mapped_column(String(16))  # breakfast / lunch / dinner / snack
    source: Mapped[str] = mapped_column(String(16))  # photo / manual / copy
    photo_upload_id: Mapped[int | None] = mapped_column(ForeignKey("uploads.id", ondelete="SET NULL"))
    kcal: Mapped[float] = mapped_column(Float, default=0)
    carb: Mapped[float] = mapped_column(Float, default=0)
    protein: Mapped[float] = mapped_column(Float, default=0)
    fat: Mapped[float] = mapped_column(Float, default=0)
    plan_code: Mapped[str | None] = mapped_column(String(32))
    plan_score: Mapped[int | None] = mapped_column(Integer)
    plan_lit: Mapped[bool] = mapped_column(Boolean, default=False)
    plan_tip: Mapped[str | None] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(String(200))

    items: Mapped[list["MealItem"]] = relationship(
        back_populates="meal", cascade="all, delete-orphan", order_by="MealItem.id"
    )


class MealItem(Base):
    __tablename__ = "meal_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    meal_id: Mapped[int] = mapped_column(ForeignKey("meal_logs.id", ondelete="CASCADE"), index=True)
    food_id: Mapped[int | None] = mapped_column(ForeignKey("foods.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(16))
    grams: Mapped[float] = mapped_column(Float)
    unit_name: Mapped[str] = mapped_column(String(8))
    unit_count: Mapped[float] = mapped_column(Float)
    kcal: Mapped[float] = mapped_column(Float)
    carb: Mapped[float] = mapped_column(Float)
    protein: Mapped[float] = mapped_column(Float)
    fat: Mapped[float] = mapped_column(Float)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    estimated: Mapped[bool] = mapped_column(Boolean, default=False)

    meal: Mapped[MealLog] = relationship(back_populates="items")


class WaterLog(Base):
    __tablename__ = "water_logs"
    __table_args__ = (UniqueConstraint("user_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date)
    cups: Mapped[int] = mapped_column(Integer, default=0)


class Challenge(TimestampMixin, Base):
    """把饮食方案当成随时可换、可停的挑战。"""

    __tablename__ = "challenges"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plan_code: Mapped[str] = mapped_column(String(32))
    days: Mapped[int] = mapped_column(Integer)  # 3 = 试玩
    start_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active / paused / done / stopped
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Routine(TimestampMixin, Base):
    __tablename__ = "routines"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(32))
    icon: Mapped[str] = mapped_column(String(16), default="star")
    cycle_days: Mapped[int] = mapped_column(Integer)
    remind_days_before: Mapped[int] = mapped_column(Integer, default=1)
    last_done_date: Mapped[date | None] = mapped_column(Date)
    snooze_until: Mapped[date | None] = mapped_column(Date)
    reminder_credits: Mapped[int] = mapped_column(Integer, default=0)  # 一次性订阅消息授权次数
    last_reminded_for: Mapped[date | None] = mapped_column(Date)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    logs: Mapped[list["RoutineLog"]] = relationship(
        back_populates="routine", cascade="all, delete-orphan", order_by="RoutineLog.done_date.desc()"
    )


class RoutineLog(TimestampMixin, Base):
    __tablename__ = "routine_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    routine_id: Mapped[int] = mapped_column(ForeignKey("routines.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    done_date: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(200))
    cost: Mapped[float | None] = mapped_column(Float)
    photo_upload_ids: Mapped[list] = mapped_column(JSON, default=list)

    routine: Mapped[Routine] = relationship(back_populates="logs")


class SymptomLog(TimestampMixin, Base):
    __tablename__ = "symptom_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    parts: Mapped[list] = mapped_column(JSON, default=list)  # [{code, label, note}]
    symptoms: Mapped[list] = mapped_column(JSON, default=list)
    severity: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime())
    temperature: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active / healed
    healed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    note: Mapped[str | None] = mapped_column(String(500))

    updates: Mapped[list["SymptomUpdate"]] = relationship(
        back_populates="symptom", cascade="all, delete-orphan", order_by="SymptomUpdate.date"
    )


class SymptomUpdate(Base):
    __tablename__ = "symptom_updates"
    __table_args__ = (UniqueConstraint("symptom_id", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    symptom_id: Mapped[int] = mapped_column(ForeignKey("symptom_logs.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date)
    severity: Mapped[int] = mapped_column(Integer)
    temperature: Mapped[float | None] = mapped_column(Float)
    note: Mapped[str | None] = mapped_column(String(200))

    symptom: Mapped[SymptomLog] = relationship(back_populates="updates")


class MedicationLog(TimestampMixin, Base):
    __tablename__ = "medication_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    symptom_id: Mapped[int | None] = mapped_column(ForeignKey("symptom_logs.id", ondelete="SET NULL"))
    name: Mapped[str] = mapped_column(String(64))
    spec: Mapped[str | None] = mapped_column(String(64))  # 规格，如 0.3g×24 粒
    dose: Mapped[str | None] = mapped_column(String(32))  # 每次剂量，如 1 粒
    times_per_day: Mapped[int | None] = mapped_column(Integer)
    course_days: Mapped[int | None] = mapped_column(Integer)
    start_date: Mapped[date] = mapped_column(Date)
    remind: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_credits: Mapped[int] = mapped_column(Integer, default=0)
    photo_upload_id: Mapped[int | None] = mapped_column(ForeignKey("uploads.id", ondelete="SET NULL"))
    note: Mapped[str | None] = mapped_column(String(200))


class MedicalRecord(TimestampMixin, Base):
    __tablename__ = "medical_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    symptom_id: Mapped[int | None] = mapped_column(ForeignKey("symptom_logs.id", ondelete="SET NULL"))
    visit_date: Mapped[date] = mapped_column(Date)
    hospital: Mapped[str | None] = mapped_column(String(64))
    department: Mapped[str | None] = mapped_column(String(32))
    diagnosis: Mapped[str | None] = mapped_column(Text)
    image_upload_ids: Mapped[list] = mapped_column(JSON, default=list)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(String(500))


class AIJob(TimestampMixin, Base):
    """每次模型调用一行，用于成本统计和排障。"""

    __tablename__ = "ai_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # inbody / food / medicine / text
    status: Mapped[str] = mapped_column(String(16))  # ok / fallback_ok / failed
    provider: Mapped[str | None] = mapped_column(String(16))
    model: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
