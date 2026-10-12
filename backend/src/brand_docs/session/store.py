"""Thread-safe in-memory session store with expiry."""

from datetime import UTC, datetime, timedelta
from threading import RLock

from pydantic import BaseModel, Field

from brand_docs.domain.models import (
    BrandData,
    BrandLogo,
    CheckResult,
    CompletenessSuggestion,
    Document,
    Grouping,
)
from brand_docs.errors import SessionNotFoundError
from brand_docs.utils.logger import setup_logger

logger = setup_logger(__name__)


class Session(BaseModel):
    """All transient data associated with one browser workflow."""

    session_id: str
    brand: BrandData
    grouping: Grouping
    suggestions: list[CompletenessSuggestion] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)
    check_results: list[CheckResult] = Field(default_factory=list)
    logo: BrandLogo | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SessionStore:
    """Store active user work in memory until its TTL expires."""

    def __init__(self, ttl: timedelta) -> None:
        self.sessions: dict[str, Session] = {}
        self.ttl = ttl
        self.lock = RLock()

    def _purge_expired(self) -> None:
        with self.lock:
            now = datetime.now(UTC)
            expired = [
                key
                for key, session in self.sessions.items()
                if now - session.created_at > self.ttl
            ]
            for key in expired:
                del self.sessions[key]

    def create(self, session: Session) -> str:
        with self.lock:
            self._purge_expired()
            self.sessions[session.session_id] = session
        return session.session_id

    def get(self, session_id: str) -> Session:
        with self.lock:
            self._purge_expired()
            session = self.sessions.get(session_id)
            if session is None:
                raise SessionNotFoundError("Session was not found or has expired.")
            return session

    def set_logo(self, session_id: str, logo: BrandLogo | None) -> None:
        with self.lock:
            session = self.get(session_id)
            session.logo = logo
