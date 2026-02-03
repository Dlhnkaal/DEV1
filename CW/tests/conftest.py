from typing import Any, Mapping, Generator
import pytest
from fastapi.testclient import TestClient
from main import app
from http import HTTPStatus


@pytest.fixture
def app_client() -> Generator[TestClient, None, None]:
    return TestClient(app)


@pytest.fixture(scope='function')
def some_user(
    app_client: TestClient,
    name: str,
    password: str,
) -> Generator[Mapping[str, Any], None, None]:
    create_response = app_client.post('/users', json=dict(
        name=name,
        password=password,
        email=f'{name.lower().replace(".", "_").replace(" ", "_")}@example.com'
    ))
    created_user = create_response.json()

    assert create_response.status_code == HTTPStatus.CREATED
    yield created_user

    deleted_response = app_client.delete(
        f'/users/{created_user["id"]}',
        cookies={
            'x-user-id': str(created_user['id'])
        },
    )
    assert deleted_response.status_code == HTTPStatus.OK or deleted_response.status_code == HTTPStatus.NOT_FOUND