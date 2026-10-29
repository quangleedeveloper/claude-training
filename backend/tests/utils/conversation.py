from sqlmodel import Session

from app.core.prompt import PERSONA_NOTICE
from app.models import (
    Conversation,
    ConversationMessage,
    MessageRole,
    Person,
    User,
)
from tests.utils.person import create_random_person


def create_random_conversation(
    db: Session, user: User | None = None, person: Person | None = None
) -> Conversation:
    """An open conversation holding only the notice, for the person's owner."""
    person = person or create_random_person(db, owner=user)
    conversation = Conversation(person_id=person.id, user_id=person.owner_id)
    db.add(conversation)
    db.add(
        ConversationMessage(
            conversation_id=conversation.id,
            role=MessageRole.PERSONA,
            content=PERSONA_NOTICE,
        )
    )
    db.commit()
    db.refresh(conversation)
    return conversation
