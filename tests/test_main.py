import time

import pytest
from fastapi.testclient import TestClient

from app.main import _DB_CARDS, app

client = TestClient(app)


@pytest.fixture
def client1() -> TestClient:
    app.dependency_overrides.clear()
    return TestClient(app)


@pytest.fixture(autouse=True)
def run_around_tests():
    global _next_card_id
    _DB_CARDS.clear()
    _next_card_id = 1
    yield
    app.dependency_overrides.clear()


# help functions


def assert_rfc7807_problem_detail(response_json: dict, expected_status: int, expected_title: str):
    assert "type" in response_json
    assert "title" in response_json
    assert "status" in response_json
    assert "detail" in response_json
    assert "correlation_id" in response_json
    assert response_json["status"] == expected_status
    assert response_json["title"] == expected_title
    assert len(response_json["correlation_id"]) > 20


# positive tests


def test_create_card_success(client1: TestClient):
    response = client1.post(
        "/cards",
        json={"title": "My first idea", "column": "todo"},
        headers={"X-User-ID": "user-1"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "My first idea"
    assert data["column"] == "todo"
    assert data["owner_id"] == "user-1"
    assert "id" in data


def test_create_card_max_title_length_succeeds(client1: TestClient):
    max_length_title = "A" * 255
    response = client1.post(
        "/cards",
        json={"title": max_length_title, "column": "done"},
        headers={"X-User-ID": "user-1"},
    )
    assert response.status_code == 201
    assert response.json()["title"] == max_length_title


# negative tests (p06)


def test_create_card_title_too_short_fails_with_rfc7807(client1: TestClient):
    response = client1.post(
        "/cards",
        json={"title": "ab", "column": "in-progress"},
        headers={"X-User-ID": "user-1"},
    )
    assert response.status_code == 422
    assert_rfc7807_problem_detail(
        response.json(), expected_status=422, expected_title="Validation Error"
    )


def test_create_card_invalid_column_fails_with_rfc7807(client1: TestClient):
    response = client1.post(
        "/cards",
        json={"title": "A valid title", "column": "invalid-column"},
        headers={"X-User-ID": "user-1"},
    )
    assert response.status_code == 422
    assert_rfc7807_problem_detail(
        response.json(), expected_status=422, expected_title="Validation Error"
    )


def test_get_another_users_card_fails(client1: TestClient):
    response_create = client1.post(
        "/cards",
        json={"title": "User-1 Card", "column": "done"},
        headers={"X-User-ID": "user-1"},
    )
    card_id = response_create.json()["id"]

    response_get = client1.get(f"/cards/{card_id}", headers={"X-User-ID": "user-2"})

    assert response_get.status_code == 403
    assert_rfc7807_problem_detail(
        response_get.json(), expected_status=403, expected_title="Access Denied"
    )


def test_get_non_existent_card_fails(client1: TestClient):
    response = client1.get("/cards/999", headers={"X-User-ID": "user-1"})
    assert response.status_code == 404
    assert_rfc7807_problem_detail(response.json(), expected_status=404, expected_title="Not Found")


def test_rate_limit_blocks_flood_requests(client1: TestClient):
    # не придумал как разрешить проблему лучше
    time.sleep(31)

    headers = {"X-User-ID": "rate-limit-tester"}
    json_payload = {"title": "Flood Request", "column": "todo"}

    for i in range(5):
        response = client1.post("/cards", json=json_payload, headers=headers)
        assert response.status_code == 201, f"Request {i + 1} should have succeeded"

    response = client1.post("/cards", json=json_payload, headers=headers)
    assert response.status_code == 429
    assert_rfc7807_problem_detail(
        response.json(), expected_status=429, expected_title="Rate Limit Exceeded"
    )


def test_create_card_with_xss_payload_is_sanitized(client1: TestClient):
    # аналогично
    time.sleep(31)

    xss_payload = "<script>alert('XSS')</script>"
    escaped_payload = "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;"

    response = client1.post(
        "/cards",
        json={"title": xss_payload, "column": "todo"},
        headers={"X-User-ID": "user-xss"},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == escaped_payload
    assert _DB_CARDS[data["id"]].title == escaped_payload


def test_update_card_success(client1: TestClient):
    response_create = client1.post(
        "/cards",
        json={"title": "Original Title", "column": "todo"},
        headers={"X-User-ID": "user-1"},
    )
    card_id = response_create.json()["id"]

    response_update = client1.patch(
        f"/cards/{card_id}",
        json={"title": "Updated Title", "column": "done"},
        headers={"X-User-ID": "user-1"},
    )

    assert response_update.status_code == 200
    data = response_update.json()
    assert data["title"] == "Updated Title"
    assert data["column"] == "done"


def test_update_another_users_card_fails(client1: TestClient):
    response_create = client1.post(
        "/cards",
        json={"title": "User-1 Card", "column": "todo"},
        headers={"X-User-ID": "user-1"},
    )
    card_id = response_create.json()["id"]

    response_update = client1.patch(
        f"/cards/{card_id}",
        json={"title": "Malicious Update"},
        headers={"X-User-ID": "user-2"},
    )

    assert response_update.status_code == 403
