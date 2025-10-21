from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# checks if answer has rfc 7807 format
def assert_rfc7807_problem_detail(
    response_json: dict, expected_status: int, expected_title: str
):
    assert "type" in response_json
    assert "title" in response_json
    assert "status" in response_json
    assert "detail" in response_json
    assert "correlation_id" in response_json
    assert response_json["status"] == expected_status
    assert response_json["title"] == expected_title
    assert len(response_json["correlation_id"]) > 20


# checks creating new card with valid info
def test_create_card_success():
    response = client.post("/cards", json={"title": "My first idea", "column": "todo"})
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "My first idea"
    assert data["column"] == "todo"
    assert "id" in data


# checks if creating card with short title ends with error
def test_create_card_title_too_short_fails_with_rfc7807():
    response = client.post("/cards", json={"title": "ab", "column": "in-progress"})

    assert response.status_code == 422
    assert_rfc7807_problem_detail(
        response.json(), expected_status=422, expected_title="Validation Error"
    )


# creates card with invalid column value
def test_create_card_invalid_column_fails_with_rfc7807():
    response = client.post(
        "/cards", json={"title": "A valid title", "column": "invalid-column"}
    )

    assert response.status_code == 422
    assert_rfc7807_problem_detail(
        response.json(), expected_status=422, expected_title="Validation Error"
    )


# creates title 255 symbol long
def test_create_card_max_title_length_succeeds():
    max_length_title = "A" * 255
    response = client.post("/cards", json={"title": max_length_title, "column": "done"})
    assert response.status_code == 201
    assert response.json()["title"] == max_length_title


# checks rate limiting
def test_rate_limit_with_sleep():
    for i in range(4):
        response = client.post(
            "/cards", json={"title": f"Card batch 1-{i}", "column": "todo"}
        )
        assert response.status_code == 201

    response = client.post(
        "/cards", json={"title": "This one should be blocked", "column": "todo"}
    )
    assert response.status_code == 429
