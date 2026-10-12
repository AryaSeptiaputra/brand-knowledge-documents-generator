"""Synchronous Ollama adapter for structured output."""

import httpx
from ollama import Client, ResponseError
from pydantic import ValidationError

from brand_docs.errors import LlmOutputError, LlmUnavailableError
from brand_docs.llm.client import T
from brand_docs.settings import Settings
from brand_docs.utils.logger import setup_logger

logger = setup_logger(__name__)


class OllamaClient:
    """Call the configured local Ollama model."""

    def __init__(self, settings: Settings) -> None:
        if settings.ollama_host:
            self.client = Client(host=settings.ollama_host)
        else:
            self.client = Client()
        self.settings = settings

    def generate(self, prompt: str, schema: type[T]) -> T:
        try:
            response = self.client.generate(
                model=self.settings.model_name,
                prompt=prompt,
                format=schema.model_json_schema(),
                options={
                    "temperature": self.settings.temperature,
                    "num_ctx": self.settings.num_ctx,
                },
            )
        except (httpx.HTTPError, ResponseError, ConnectionError, OSError) as error:
            logger.error("Ollama request failed", exc_info=True)
            raise LlmUnavailableError("The local language model is unavailable.") from error
        try:
            return schema.model_validate_json(response.response or "")
        except (ValidationError, ValueError) as error:
            logger.error("Ollama returned invalid structured output", exc_info=True)
            raise LlmOutputError("The local language model returned invalid output.") from error
