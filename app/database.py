import psycopg2
from sqlalchemy_utils import database_exists, create_database
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.core.config import settings
from sqlalchemy.engine.url import make_url

Base = declarative_base()

# Sync database setup
try:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        echo=False  # Set to True for SQL debugging
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    print(f"[DB ERROR] Could not create engine or session: {e}")
    engine = None
    SessionLocal = None

# Async database setup for async operations
try:
    async_engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        echo=False
    )
    AsyncSessionLocal = sessionmaker(
        async_engine, class_=AsyncSession, expire_on_commit=False
    )
except Exception as e:
    print(f"[DB ERROR] Could not create async engine or session: {e}")
    async_engine = None
    AsyncSessionLocal = None

url = make_url(settings.DATABASE_URL)

def ensure_database_exists():
    """
    Checks if the database exists, and creates it if it does not.
    """
    try:
        if not database_exists(settings.DATABASE_URL):
            create_database(settings.DATABASE_URL)
            print(f"Database created: {settings.DATABASE_URL}")
        else:
            print(f"Database already exists: {settings.DATABASE_URL}")
    except Exception as e:
        print(f"[DB ERROR] Could not check or create database: {e}")

def init_db():
    try:
        ensure_database_exists()
        from app.models.admin import AdminUser, AdminDetails
        from app.models.student import Student, StudentAttendance, StudentMessage, StudentTask, StudentExam
        from app.models.booking import SeatBooking
        from app.models.referral import ReferralCode, Referral
        from app.models.subscription import SubscriptionPlan
        # Only create tables, do not try to create the database itself for cloud DBs
        if engine is not None:
            Base.metadata.create_all(bind=engine)
        else:
            print("[DB ERROR] Engine is None, cannot create tables.")
    except Exception as e:
        print(f"[DB ERROR] init_db failed: {e}")

# Dependency to get database session
def get_db():
    if SessionLocal is None:
        raise Exception("[DB ERROR] SessionLocal is None, cannot get DB session.")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Async dependency to get database session
async def get_async_db():
    if AsyncSessionLocal is None:
        raise Exception("[DB ERROR] AsyncSessionLocal is None, cannot get async DB session.")
    async with AsyncSessionLocal() as session:
        yield session
