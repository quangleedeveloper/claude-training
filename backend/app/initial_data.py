import logging

from sqlmodel import Session

from app.core.checkpoint import setup_checkpoint_tables
from app.core.db import engine, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init() -> None:
    with Session(engine) as session:
        init_db(session)


def main() -> None:
    logger.info("Creating initial data")
    init()
    logger.info("Initial data created")
    logger.info("Creating LangGraph checkpoint tables")
    setup_checkpoint_tables()


if __name__ == "__main__":
    main()
