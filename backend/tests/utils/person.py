from sqlmodel import Session

from app import crud
from app.models import MemoryOffer, Person, PersonCreate, PersonMember, User
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def create_random_person(db: Session, owner: User | None = None) -> Person:
    user = owner or create_random_user(db)
    person_in = PersonCreate(
        name=random_lower_string(), other_names=[random_lower_string()]
    )
    return crud.create_person(session=db, person_in=person_in, owner_id=user.id)


def add_member(db: Session, person: Person, user: User | None = None) -> User:
    """Make `user` (default: a new account) a member of `person`; returns them."""
    member = user or create_random_user(db)
    db.add(PersonMember(person_id=person.id, user_id=member.id, adult_confirmed=True))
    db.commit()
    return member


def create_random_offer(
    db: Session,
    person: Person,
    user: User | None = None,
    content: str = "She sang while she cooked.",
) -> MemoryOffer:
    """A waiting offer for `person` from `user` (default: a new account)."""
    offer = MemoryOffer(
        person_id=person.id,
        from_user_id=(user or create_random_user(db)).id,
        content=content,
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return offer
