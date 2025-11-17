import html
import logging
from enum import Enum
from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="SecDev Course App",
    version="0.1.0",
)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


# --- ADR-002: RFC 7807 ---
class AppException(Exception):
    def __init__(self, status_code: int, title: str, detail: str):
        self.status_code = status_code
        self.title = title
        self.detail = detail


# helper for generating rfc 7807 answers
def problem_json_response(
    status_code: int, title: str, detail: str, type_url: str = "about:blank"
):
    correlation_id = str(uuid4())
    logger.error(
        f"Error {correlation_id}: status={status_code}, "
        f"title='{title}', detail='{detail}'"
    )
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


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return problem_json_response(exc.status_code, exc.title, exc.detail)


# rfc 7807 exception handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return problem_json_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "Validation Error",
        "Input validation failed.",
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    response = problem_json_response(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Rate Limit Exceeded",
        f"Rate limit exceeded: {exc.detail}",
    )
    if exc.headers:
        response.headers.update(exc.headers)
    return response


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return problem_json_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        "Internal Server Error",
        "An unexpected error occurred on the server.",
    )


# --- business logic ---


class CardColumn(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in-progress"
    DONE = "done"


# ADR-001: input data validation
class CardCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    column: CardColumn

    @field_validator("title")
    @classmethod
    def sanitize(cls, value: str) -> str:
        return html.escape(value)


class CardUpdate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    column: Optional[CardColumn] = None

    @field_validator("title")
    @classmethod
    def sanitize(cls, value: str) -> str:
        if value is not None:
            return html.escape(value)
        return value


class Card(BaseModel):
    id: int
    title: str
    column: CardColumn
    owner_id: str


# --- db ---

_DB_CARDS: Dict[int, Card] = {}
_next_card_id = 1


def get_current_user_id(request: Request) -> str:
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise AppException(
            status.HTTP_401_UNAUTHORIZED,
            "Authentication Error",
            "X-User-ID header is missing.",
        )
    return user_id


# --- api ---


@app.get("/health")
@limiter.limit("5/30second")
def health(request: Request):
    return {"status": "ok"}


@app.post("/cards", response_model=Card, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/30second")  # ADR-003: Rate Limiting
def create_card(
    card_in: CardCreate, request: Request, owner_id: str = Depends(get_current_user_id)
):
    global _next_card_id
    new_card = Card(id=_next_card_id, owner_id=owner_id, **card_in.model_dump())
    _DB_CARDS[_next_card_id] = new_card
    _next_card_id += 1
    return new_card


@app.get("/cards", response_model=List[Card])
def get_cards_list(request: Request, owner_id: str = Depends(get_current_user_id)):
    return [card for card in _DB_CARDS.values() if card.owner_id == owner_id]


@app.get("/cards/{card_id}", response_model=Card)
def get_card_by_id(
    request: Request, card_id: int, owner_id: str = Depends(get_current_user_id)
):
    card = _DB_CARDS.get(card_id)
    if not card:
        raise AppException(
            status.HTTP_404_NOT_FOUND, "Not Found", f"Card with id={card_id} not found."
        )

    if card.owner_id != owner_id:
        raise AppException(
            status.HTTP_403_FORBIDDEN,
            "Access Denied",
            "You do not have permission to access this card.",
        )
    return card


@app.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def delete_card(
    request: Request, card_id: int, owner_id: str = Depends(get_current_user_id)
):
    card = _DB_CARDS.get(card_id)
    if not card:
        raise AppException(
            status.HTTP_404_NOT_FOUND, "Not Found", f"Card with id={card_id} not found."
        )

    if card.owner_id != owner_id:
        raise AppException(
            status.HTTP_403_FORBIDDEN,
            "Access Denied",
            "You do not have permission to delete this card.",
        )

    del _DB_CARDS[card_id]


@app.patch("/cards/{card_id}", response_model=Card)
@limiter.limit("10/minute")
def update_card(
    request: Request,
    card_id: int,
    card_in: CardUpdate,
    owner_id: str = Depends(get_current_user_id),
):
    card = _DB_CARDS.get(card_id)
    if not card:
        raise AppException(
            status.HTTP_404_NOT_FOUND, "Not Found", f"Card with id={card_id} not found."
        )

    if card.owner_id != owner_id:
        raise AppException(
            status.HTTP_403_FORBIDDEN,
            "Access Denied",
            "You do not have permission to update this card.",
        )

    update_data = card_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(card, field, value)

    _DB_CARDS[card_id] = card
    return card
