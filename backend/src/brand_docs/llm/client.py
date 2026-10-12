"""Language model protocol and schemas used by structured composition."""

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LlmClient(Protocol):
    """Adapter contract for structured local-model output."""

    def generate(self, prompt: str, schema: type[T]) -> T:
        """Generate and validate a structured response."""
        ...


class FakeLlmClient:
    """Return a test-provided structured response without contacting a model runner."""

    def __init__(self, response: BaseModel) -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str, schema: type[T]) -> T:
        self.prompts.append(prompt)
        return schema.model_validate(self.response.model_dump())
