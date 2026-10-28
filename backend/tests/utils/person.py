from sqlmodel import Session

from app import crud
from app.models import Person, PersonCreate, User
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def create_random_person(db: Session, owner: User | None = None) -> Person:
    user = owner or create_random_user(db)
    person_in = PersonCreate(
        name=random_lower_string(), other_names=[random_lower_string()]
    )
    return crud.create_person(session=db, person_in=person_in, owner_id=user.id)
