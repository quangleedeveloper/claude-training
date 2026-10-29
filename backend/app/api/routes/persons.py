import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, delete, func, select

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    ConversationSummary,
    MemberInvite,
    MemberPublic,
    MembersPublic,
    Message,
    Person,
    PersonCreate,
    PersonMember,
    PersonPublic,
    PersonsPublic,
    PersonUpdate,
    User,
)
from app.services.conversation_summary import end_member_conversations

router = APIRouter(prefix="/persons", tags=["persons"])
logger = logging.getLogger(__name__)

# The same answer whether or not the address belongs to an account (no enumeration)
INVITE_ANSWER = "If an account exists for that email it can now talk with this persona."


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
    """The one place that decides who may reach a persona: its owner, or someone the
    owner invited. Superusers get no extra access."""
    person = session.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    if person.owner_id == user.id:
        return person
    member = session.exec(
        select(PersonMember.id).where(
            col(PersonMember.person_id) == person_id,
            col(PersonMember.user_id) == user.id,
        )
    ).first()
    if member is None:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return person


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


@router.post("/{id}/members", response_model=Message)
def invite_member(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    invite_in: MemberInvite,
) -> Any:
    """
    Let an existing account talk with this person's persona (owner only).
    """
    person = get_person_or_error(session, current_user, id)
    invited = crud.get_user_by_email(session=session, email=invite_in.email)
    if invited and invited.is_active and invited.id != person.owner_id:
        already = session.exec(
            select(PersonMember.id).where(
                col(PersonMember.person_id) == person.id,
                col(PersonMember.user_id) == invited.id,
            )
        ).first()
        if already is None:
            session.add(
                PersonMember(
                    person_id=person.id, user_id=invited.id, adult_confirmed=True
                )
            )
            try:
                session.commit()
                logger.info(
                    "member invited: person=%s member=%s", person.id, invited.id
                )
            except IntegrityError:
                # Two invites at once: the other one already stored it
                session.rollback()
    return Message(message=INVITE_ANSWER)


@router.get("/{id}/members", response_model=MembersPublic)
def read_members(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    List the accounts invited to talk with this person's persona (owner only).
    """
    person = get_person_or_error(session, current_user, id)
    rows = session.exec(
        select(PersonMember, User)
        .join(User, col(User.id) == col(PersonMember.user_id))
        .where(col(PersonMember.person_id) == person.id)
        .order_by(col(PersonMember.invited_at))
    ).all()
    members = [
        MemberPublic(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            invited_at=member.invited_at,
        )
        for member, user in rows
    ]
    return MembersPublic(data=members, count=len(members))


@router.delete("/{id}/members/{user_id}", response_model=Message)
def revoke_member(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    user_id: uuid.UUID,
) -> Any:
    """
    Take a member's access away: their open conversations end without a summary and
    their summary is deleted (owner only).
    """
    person = get_person_or_error(session, current_user, id)
    member = session.exec(
        select(PersonMember).where(
            col(PersonMember.person_id) == person.id,
            col(PersonMember.user_id) == user_id,
        )
    ).first()
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")
    # One commit, no model call: a crash cannot leave a revoked member with a live
    # chat that the idle sweep would later summarize
    end_member_conversations(session, person.id, user_id)
    session.exec(
        delete(ConversationSummary).where(
            col(ConversationSummary.person_id) == person.id,
            col(ConversationSummary.user_id) == user_id,
        )
    )
    session.delete(member)
    session.commit()
    logger.info("member revoked: person=%s member=%s", person.id, user_id)
    return Message(message="Member removed")
