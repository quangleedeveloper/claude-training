import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlmodel import Session, col, func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Message,
    Person,
    PersonCreate,
    PersonPublic,
    PersonsPublic,
    PersonUpdate,
    User,
)

router = APIRouter(prefix="/persons", tags=["persons"])


def get_person_or_error(session: Session, user: User, person_id: uuid.UUID) -> Person:
    """Return the person if it is the user's own; superusers get no extra access."""
    person = session.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    if person.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return person


def get_person_for_conversation(
    session: Session, user: User, person_id: uuid.UUID
) -> Person:
    """The one place that decides who may reach a persona (owner only for now)."""
    return get_person_or_error(session, user, person_id)


@router.get("/", response_model=PersonsPublic)
def read_persons(
    session: SessionDep, current_user: CurrentUser, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve the caller's persons.
    """
    count = session.exec(
        select(func.count())
        .select_from(Person)
        .where(Person.owner_id == current_user.id)
    ).one()
    persons = session.exec(
        select(Person)
        .where(Person.owner_id == current_user.id)
        .order_by(col(Person.created_at).desc())
        .offset(skip)
        .limit(limit)
    ).all()
    persons_public = [PersonPublic.model_validate(person) for person in persons]
    return PersonsPublic(data=persons_public, count=count)


@router.get("/{id}", response_model=PersonPublic)
def read_person(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    Get person by ID.
    """
    return get_person_or_error(session, current_user, id)


@router.post("/", response_model=PersonPublic)
def create_person(
    *, session: SessionDep, current_user: CurrentUser, person_in: PersonCreate
) -> Any:
    """
    Create new person.
    """
    return crud.create_person(
        session=session, person_in=person_in, owner_id=current_user.id
    )


@router.patch("/{id}", response_model=PersonPublic)
def update_person(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    person_in: PersonUpdate,
) -> Any:
    """
    Update a person's name or other names.
    """
    person = get_person_or_error(session, current_user, id)
    person.sqlmodel_update(person_in.model_dump(exclude_unset=True))
    session.add(person)
    session.commit()
    session.refresh(person)
    return person


@router.delete("/{id}")
def delete_person(
    session: SessionDep, current_user: CurrentUser, id: uuid.UUID
) -> Message:
    """
    Delete a person; their memories stay and are unlinked.
    """
    person = get_person_or_error(session, current_user, id)
    session.delete(person)
    session.commit()
    return Message(message="Person deleted successfully")
