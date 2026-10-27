from sqlmodel import Session

from app import crud
from app.models import Memory, MemoryCreate, User
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def create_random_memory(db: Session, owner: User | None = None) -> Memory:
    user = owner or create_random_user(db)
    owner_id = user.id
    assert owner_id is not None
    memory_in = MemoryCreate(
        title=random_lower_string(),
        person_name=random_lower_string(),
        content=random_lower_string(),
    )
    return crud.create_memory(session=db, memory_in=memory_in, owner_id=owner_id)
