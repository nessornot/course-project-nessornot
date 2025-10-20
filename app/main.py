from enum import Enum
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, constr
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(title="SecDev Course App", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# helper for generating rfc 7807 answers
def problem_json_response(
    status_code: int, title: str, detail: str, type_url: str = "about:blank"
):
    correlation_id = str(uuid4())
    return JSONResponse(
        status_code=status_code,
        content={
            "type": type_url,
            "title": title,
            "status": status_code,
            "detail": detail,
            "correlation_id": correlation_id,
        },
    )


# rfc 7807 exception handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return problem_json_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        title="Validation Error",
        detail="One or more fields failed validation.",
    )


# old exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # Normalize FastAPI HTTPException into our error envelope
    detail = exc.detail if isinstance(exc.detail, str) else "http_error"
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "http_error", "message": detail}},
    )


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return problem_json_response(
        status_code=exc.status,
        title=exc.code.replace("_", " ").title(),
        detail=exc.message,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


# Example minimal entity (for tests/demo)
_DB = {"items": []}


@app.post("/items")
def create_item(name: str):
    if not name or len(name) > 100:
        raise ApiError(
            code="validation_error", message="name must be 1..100 chars", status=422
        )
    item = {"id": len(_DB["items"]) + 1, "name": name}
    _DB["items"].append(item)
    return item


@app.get("/items/{item_id}")
def get_item(item_id: int):
    for it in _DB["items"]:
        if it["id"] == item_id:
            return it
    raise ApiError(code="not_found", message="item not found", status=404)


class CardColumn(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in-progress"
    DONE = "done"


class CardCreate(BaseModel):
    title: constr(min_length=3, max_length=255)
    column: CardColumn


_DB_CARDS = []


# ADR-003: применение Rate Limiting
@app.post("/cards", status_code=status.HTTP_201_CREATED)
@limiter.limit("6/second")
def create_card(card: CardCreate, request: Request):
    new_card = {"id": len(_DB_CARDS) + 1, **card.model_dump()}
    _DB_CARDS.append(new_card)
    return new_card
