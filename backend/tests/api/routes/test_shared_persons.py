import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.models import User
from tests.utils.person import add_member, create_random_person
from tests.utils.user import authentication_token_from_email, create_random_user

SHARED_URL = f"{settings.API_V1_STR}/persons/shared"


def get_normal_user(db: Session) -> User:
    user = crud.get_user_by_email(session=db, email=settings.EMAIL_TEST_USER)
    assert user is not None
    return user


def test_read_shared_persons(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = create_random_person(db)
    add_member(db, person, get_normal_user(db))
    response = client.get(SHARED_URL, headers=normal_user_token_headers)
    assert response.status_code == 200
    content = response.json()
    assert {"id": str(person.id), "name": person.name} in content["data"]
    assert content["count"] == len(content["data"])


def test_read_shared_persons_shows_only_id_and_name(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = create_random_person(db)
    add_member(db, person, get_normal_user(db))
    response = client.get(SHARED_URL, headers=normal_user_token_headers)
    entry = next(p for p in response.json()["data"] if p["id"] == str(person.id))
    assert set(entry) == {"id", "name"}


def test_read_shared_persons_outsider_gets_empty_list(
    client: TestClient, db: Session
) -> None:
    person = create_random_person(db)
    add_member(db, person)
    outsider = create_random_user(db)
    headers = authentication_token_from_email(
        client=client, email=outsider.email, db=db
    )
    response = client.get(SHARED_URL, headers=headers)
    assert response.status_code == 200
    assert response.json() == {"data": [], "count": 0}


def test_read_shared_persons_superuser_gets_no_extra_rows(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    person = create_random_person(db)
    add_member(db, person)
    response = client.get(SHARED_URL, headers=superuser_token_headers)
    assert response.status_code == 200
    assert str(person.id) not in [p["id"] for p in response.json()["data"]]


def test_read_shared_persons_leaves_out_own_persons(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    own = create_random_person(db, owner=get_normal_user(db))
    response = client.get(SHARED_URL, headers=normal_user_token_headers)
    assert response.status_code == 200
    assert str(own.id) not in [p["id"] for p in response.json()["data"]]


def test_read_shared_persons_revoked_member_loses_it(
    client: TestClient, normal_user_token_headers: dict[str, str], db: Session
) -> None:
    person = create_random_person(db)
    member = add_member(db, person, get_normal_user(db))
    owner_headers = authentication_token_from_email(
        client=client, email=_owner_email(db, person.owner_id), db=db
    )
    revoke = client.delete(
        f"{settings.API_V1_STR}/persons/{person.id}/members/{member.id}",
        headers=owner_headers,
    )
    assert revoke.status_code == 200
    response = client.get(SHARED_URL, headers=normal_user_token_headers)
    assert str(person.id) not in [p["id"] for p in response.json()["data"]]


def test_read_shared_persons_is_not_parsed_as_an_id(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(SHARED_URL, headers=normal_user_token_headers)
    assert response.status_code == 200


def test_read_shared_persons_requires_login(client: TestClient) -> None:
    response = client.get(SHARED_URL)
    assert response.status_code == 401


def _owner_email(db: Session, owner_id: uuid.UUID) -> str:
    owner = db.get(User, owner_id)
    assert owner is not None
    return owner.email
