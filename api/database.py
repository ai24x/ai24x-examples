from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import settings

# Create database engine
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False,  # Set to True for SQL logging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Initialize database
def init_db():
    from sqlalchemy import text

    from models import (  # noqa: F401
        ApiKey,
        AuthUser,
        Base,
        BillingLedger,
        InviteCode,
        Referral,
        TokenCreditLot,
        TokenPayOrder,
        TokenWallet,
    )

    Base.metadata.create_all(bind=engine)
    # 软迁移：已有表补列（不碰 a1 表）
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "ALTER TABLE token_wallets "
                    "ADD COLUMN IF NOT EXISTS vip_expires_at TIMESTAMP WITH TIME ZONE"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE auth_users "
                    "ADD COLUMN IF NOT EXISTS frozen_at TIMESTAMP WITH TIME ZONE"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE auth_users "
                    "ADD COLUMN IF NOT EXISTS freeze_reason VARCHAR(255)"
                )
            )
    except Exception:
        pass
