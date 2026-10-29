import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, delete, func, select

from app import crud
from app.api.deps import CurrentUser, LLMClientDep, SessionDep
from app.models import (
    ConversationSummary,
    MemberInvite,
    MemberPublic,
    MembersPublic,
    Memory,
    MemoryOffer,
    MemoryPublic,
    Message,
    OfferCreate,
    OfferPublic,
    OffersPublic,
    Person,
    PersonCreate,
    PersonMember,
    PersonPublic,
    PersonsPublic,
    PersonUpdate,
    User,
)
from app.services.conversation_summary import end_member_conversations
from app.services.processing import extract_memory_story

router = APIRouter(prefix="/persons", tags=["persons"])
logger = logging.getLogger(__name__)

# The same answer whether or not the address belongs to an account (no enumeration)
INVITE_ANSWER = "If an account exists for that email it can now talk with this persona."
# Keeps one member from filling the owner's list of offers to review
MAX_WAITING_OFFERS = 20
OFFER_TITLE_CHARS = 60


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


def get_offer_or_error(
    session: Session, person_id: uuid.UUID, offer_id: uuid.UUID, *, lock: bool = False
) -> MemoryOffer:
    """An offer of this person; an id from another person is a 404, never a leak."""
    statement = select(MemoryOffer).where(
        col(MemoryOffer.id) == offer_id, col(MemoryOffer.person_id) == person_id
    )
    if lock:
        statement = statement.with_for_update()
    offer = session.exec(statement).first()
    if offer is None:
        raise HTTPException(status_code=404, detail="Offer not found")
    return offer


@router.post("/{id}/offers", response_model=Message)
def create_offer(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    offer_in: OfferCreate,
) -> Any:
    """
    Offer a memory to the family; the owner decides whether it becomes one.
    """
    person = get_person_for_conversation(session, current_user, id)
    waiting = session.exec(
        select(func.count())
        .select_from(MemoryOffer)
        .where(
            col(MemoryOffer.person_id) == person.id,
            col(MemoryOffer.from_user_id) == current_user.id,
        )
    ).one()
    if waiting >= MAX_WAITING_OFFERS:
        raise HTTPException(
            status_code=409,
            detail="Too many offers are waiting for the family to review",
        )
    offer = MemoryOffer(
        person_id=person.id, from_user_id=current_user.id, content=offer_in.content
    )
    session.add(offer)
    session.commit()
    logger.info("memory offered: person=%s offer=%s", person.id, offer.id)
    return Message(message="Your offer was sent to the family.")


@router.get("/{id}/offers", response_model=OffersPublic)
def read_offers(session: SessionDep, current_user: CurrentUser, id: uuid.UUID) -> Any:
    """
    List the memories offered for this person, newest first (owner only).
    """
    person = get_person_or_error(session, current_user, id)
    rows = session.exec(
        select(MemoryOffer, User)
        .join(User, col(User.id) == col(MemoryOffer.from_user_id))
        .where(col(MemoryOffer.person_id) == person.id)
        .order_by(col(MemoryOffer.created_at).desc())
    ).all()
    offers = [
        OfferPublic(
            id=offer.id,
            content=offer.content,
            from_name=user.full_name or user.email,
            created_at=offer.created_at,
        )
        for offer, user in rows
    ]
    return OffersPublic(data=offers, count=len(offers))


@router.post("/{id}/offers/{offer_id}/accept", response_model=MemoryPublic)
def accept_offer(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    llm: LLMClientDep,
    background_tasks: BackgroundTasks,
    id: uuid.UUID,
    offer_id: uuid.UUID,
) -> Any:
    """
    Turn an offer into one of the owner's memories, linked to this person. Its items
    start unconfirmed, so the persona cannot use them until the owner confirms them.
    """
    person = get_person_or_error(session, current_user, id)
    # Locked, so a double click cannot make two memories out of one offer
    offer = get_offer_or_error(session, person.id, offer_id, lock=True)
    memory = Memory(
        title=f"Offered: {offer.content[:OFFER_TITLE_CHARS]}".strip(),
        person_name=person.name,
        content=offer.content,
        owner_id=current_user.id,
        person_id=person.id,
    )
    session.add(memory)
    session.delete(offer)
    session.commit()
    session.refresh(memory)
    logger.info("offer accepted: person=%s memory=%s", person.id, memory.id)
    background_tasks.add_task(extract_memory_story, memory.id, llm)
    return memory


@router.delete("/{id}/offers/{offer_id}", response_model=Message)
def decline_offer(
    session: SessionDep,
    current_user: CurrentUser,
    id: uuid.UUID,
    offer_id: uuid.UUID,
) -> Any:
    """
    Decline an offer: it is deleted (owner only).
    """
    person = get_person_or_error(session, current_user, id)
    offer = get_offer_or_error(session, person.id, offer_id)
    session.delete(offer)
    session.commit()
    logger.info("offer declined: person=%s offer=%s", person.id, offer_id)
    return Message(message="Offer declined")
