from collections.abc import Callable

import pytest
from mcp import Client
from sqlmodel import Session, col, select

from app.models import PersonMember, User
from tests.utils.mcp import call, listed
from tests.utils.person import add_member, create_random_person
from tests.utils.user import create_random_user, get_superuser

pytestmark = pytest.mark.anyio


async def test_list_personas_owner_and_member(
    client: Client, db: Session, sign_in: Callable[[User], str]
) -> None:
    user = create_random_user(db)
    owned = create_random_person(db, user)
    shared = create_random_person(db)
    add_member(db, shared, user)
    sign_in(user)

    items = listed(await call(client, "list_personas"))

    assert {item["id"]: item["role"] for item in items} == {
        str(owned.id): "owner",
        str(shared.id): "member",
    }
    assert {item["name"] for item in items} == {owned.name, shared.name}
    assert all(set(item) == {"id", "name", "role"} for item in items)


async def test_list_personas_hides_unshared(
    client: Client, db: Session, sign_in: Callable[[User], str]
) -> None:
    user = create_random_user(db)
    create_random_person(db)
    sign_in(user)

    assert listed(await call(client, "list_personas")) == []


async def test_list_personas_after_revoke(
    client: Client, db: Session, sign_in: Callable[[User], str]
) -> None:
    user = create_random_user(db)
    shared = create_random_person(db)
    add_member(db, shared, user)
    sign_in(user)
    assert len(listed(await call(client, "list_personas"))) == 1

    for member in db.exec(
        select(PersonMember).where(col(PersonMember.user_id) == user.id)
    ).all():
        db.delete(member)
    db.commit()

    assert listed(await call(client, "list_personas")) == []


async def test_list_personas_empty(
    client: Client, db: Session, sign_in: Callable[[User], str]
) -> None:
    sign_in(create_random_user(db))

    result = await call(client, "list_personas")

    assert not result.is_error
    assert listed(result) == []


async def test_list_personas_scope(
    client: Client, db: Session, sign_in: Callable[[User], str]
) -> None:
    owner = create_random_user(db)
    stranger = create_random_user(db)
    private = create_random_person(db, owner)
    sign_in(stranger)
    stranger_sees = {item["id"] for item in listed(await call(client, "list_personas"))}

    sign_in(get_superuser(db))
    superuser_sees = {
        item["id"] for item in listed(await call(client, "list_personas"))
    }

    assert str(private.id) not in stranger_sees
    assert str(private.id) not in superuser_sees
