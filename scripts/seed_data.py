from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.security import hash_password
from src.db.models.user import User
from src.db.session import SessionLocal


def run() -> None:
    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == "demo@airuntime.dev").first()
        if existing:
            return
        user = User(
            email="demo@airuntime.dev",
            password_hash=hash_password("demo12345"),
            credits_balance=settings.default_user_credits,
            is_verified=True,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    run()
