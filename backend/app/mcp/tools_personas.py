import uuid
from typing import Literal

from mcp.server import MCPServer
from pydantic import BaseModel
from sqlmodel import Session

from app import crud
from app.mcp.calls import run_as_user
from app.models import User


class PersonaListing(BaseModel):
    """What the assistant may know about a person: never the owner or the record."""

    id: uuid.UUID
    name: str
    role: Literal["owner", "member"]


def list_personas_for(session: Session, user: User) -> list[PersonaListing]:
    listings = [
        PersonaListing(id=person.id, name=person.name, role="owner")
        for person in crud.list_owned_persons(session=session, owner_id=user.id)
    ]
    owned = {listing.id for listing in listings}
    listings.extend(
        PersonaListing(id=person.id, name=person.name, role="member")
        for person in crud.list_shared_persons(session=session, user_id=user.id)
        if person.id not in owned
    )
    return listings


def register(server: MCPServer) -> None:
    @server.tool()
    async def list_personas() -> list[PersonaListing]:
        """List the people whose memories you may use: yours and those shared with you."""
        return await run_as_user("list_personas", list_personas_for)
