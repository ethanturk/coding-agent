from sqlalchemy import text

from app.db.base import Base
from app.db.session import engine
from app.models import *  # noqa: F401,F403


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for column in [
            'inspect_command',
            'test_command',
            'build_command',
            'lint_command',
        ]:
            conn.execute(text(f'ALTER TABLE projects ADD COLUMN IF NOT EXISTS {column} TEXT'))


if __name__ == "__main__":
    init_db()
