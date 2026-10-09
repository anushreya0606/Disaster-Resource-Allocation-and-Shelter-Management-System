from contextlib import contextmanager

from sqlalchemy.orm import Session


@contextmanager
def transaction(db: Session):
    """
    Manage a database transaction.

    If all operations succeed:
        COMMIT

    If any operation fails:
        ROLLBACK
    """

    try:
        yield db
        db.commit()

    except Exception:
        db.rollback()
        raise