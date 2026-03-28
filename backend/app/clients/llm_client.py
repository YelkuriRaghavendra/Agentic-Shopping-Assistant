"""
LLM Client.

Wraps OpenAI / Azure OpenAI.
Single responsibility: make LLM API calls.
Services never import openai directly — they use this client.

Supports:
  - Standard OpenAI
  - Azure OpenAI
  - Tool-calling (agent picks tools)
  - Streaming (SSE token-by-token)
  - Automatic fallback to cheaper model on failure
"""

import json
from dataclasses import dataclass
from collections.abc import AsyncIterator
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import openai
from openai import AsyncOpenAI, AsyncAzureOpenAI

from app.config.loader import prompts
from app.core.config import get_settings
from app.core.exceptions import LLMError
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


@dataclass
class SuggestionItem:
    """A single suggestion from the LLM."""
    label:   str
    message: str


@dataclass
class LLMResult:
    """Returned by non-streaming LLM calls."""
    content:      str
    input_tokens: int
    output_tokens: int
    model:        str
    suggestions:  list[SuggestionItem] | None = None


@dataclass
class ToolCall:
    """Returned when the LLM decides to call a tool."""
    tool_name: str
    tool_args: dict
    model:     str


def _build_client() -> AsyncOpenAI | AsyncAzureOpenAI:
    """
    Factory: returns the right client based on USE_AZURE setting.
    Called once at module load time.
    """
    if settings.USE_AZURE:
        if not settings.AZURE_OPENAI_ENDPOINT:
            raise ValueError(
                "USE_AZURE=true but AZURE_OPENAI_ENDPOINT is not set in .env"
            )
        logger.info(
            "llm_client.mode",
            provider="azure",
            endpoint=settings.AZURE_OPENAI_ENDPOINT,
        )
        return AsyncAzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_version=settings.AZURE_OPENAI_API_VERSION,
        )

    logger.info("llm_client.mode", provider="openai", model=settings.OPENAI_CHAT_MODEL)
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def _model(fallback: bool = False) -> str:
    """
    Returns the model/deployment name.
    Azure uses deployment names; standard OpenAI uses model names.
    """
    if settings.USE_AZURE:
        name = (
            settings.AZURE_OPENAI_DEPLOYMENT_FALLBACK
            if fallback else
            settings.AZURE_OPENAI_DEPLOYMENT_CHAT
        )
        if not name:
            key = "AZURE_OPENAI_DEPLOYMENT_FALLBACK" if fallback else "AZURE_OPENAI_DEPLOYMENT_CHAT"
            raise ValueError(f"USE_AZURE=true but {key} is not set in .env")
        return name

    return settings.OPENAI_FALLBACK_MODEL if fallback else settings.OPENAI_CHAT_MODEL


# Singleton client — one per process
_client = _build_client()


class LLMClient:
    """
    All LLM operations go through this class.
    Inject as a dependency — never instantiate directly in services.
    """

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(min=1, max=5),
        retry=retry_if_exception_type(openai.RateLimitError),
        reraise=True,
    )
    async def _call(
        self,
        messages: list[dict],
        model: str,
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
        stream: bool = False,
        response_format: dict | None = None,
    ):
        """Raw API call — wraps all OpenAI/Azure specifics."""
        try:
            kwargs: dict = dict(
                model=model,
                temperature=settings.OPENAI_TEMPERATURE,
                max_tokens=settings.OPENAI_MAX_TOKENS,
                messages=messages,
                stream=stream,
            )
            if tools:
                kwargs["tools"] = tools
                kwargs["tool_choice"] = tool_choice
            if response_format:
                kwargs["response_format"] = response_format

            return await _client.chat.completions.create(**kwargs)
        except openai.RateLimitError:
            logger.warning("llm_client.rate_limited", model=model)
            raise
        except openai.APIError as exc:
            logger.error("llm_client.api_error", model=model, error=str(exc))
            raise LLMError(str(exc)) from exc

    async def decide_tool(
        self,
        system_prompt: str,
        user_message: str,
        history: list[dict],
        tools: list[dict],
    ) -> ToolCall:
        """
        First LLM call in the agent loop.
        The model reads the conversation and decides which tool to invoke.
        Falls back to cheaper model if primary fails.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user",   "content": user_message},
        ]

        response = None
        for fallback in (False, True):
            try:
                response = await self._call(
                    messages=messages,
                    model=_model(fallback),
                    tools=tools,
                    tool_choice="auto",
                )
                break
            except (LLMError, openai.RateLimitError):
                if fallback:
                    raise LLMError("Both primary and fallback models failed.")
                logger.warning("llm_client.falling_back_to_cheap_model")

        if response is None:
            raise LLMError("No response from LLM.")

        choice = response.choices[0]

        # Model chose a tool
        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            tc = choice.message.tool_calls[0]
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            logger.info("llm_client.tool_chosen", tool=tc.function.name)
            return ToolCall(
                tool_name=tc.function.name,
                tool_args=args,
                model=response.model,
            )

        # Model answered directly — wrap as direct_answer
        return ToolCall(
            tool_name="direct_answer",
            tool_args={"content": choice.message.content or ""},
            model=response.model,
        )

    async def generate(
        self,
        system_prompt: str,
        user_message: str,
        history: list[dict],
        tool_result_summary: str,
        tool_name: str,
    ) -> LLMResult:
        """
        Second LLM call — writes a natural language response
        using the tool result as context.
        Returns JSON with answer + suggestions.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user",    "content": user_message},
            {
                "role": "assistant",
                "content": f"[Tool: {tool_name}]\n[Result]: {tool_result_summary}",
            },
            {
                "role": "user",
                "content": prompts()["inline"]["generate_json_instruction"],
            },
        ]

        response = None
        for fallback in (False, True):
            try:
                response = await self._call(
                    messages=messages,
                    model=_model(fallback),
                    response_format={"type": "json_object"},
                )
                break
            except (LLMError, openai.RateLimitError):
                if fallback:
                    raise LLMError("Both primary and fallback models failed.")

        if response is None:
            raise LLMError("No response from LLM.")

        choice = response.choices[0]
        raw_content = choice.message.content or ""

        # Parse JSON response
        content, suggestions = self._parse_json_response(raw_content)

        return LLMResult(
            content=content,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            model=response.model,
            suggestions=suggestions,
        )

    @staticmethod
    def _parse_json_response(raw: str) -> tuple[str, list[SuggestionItem] | None]:
        """Parse LLM JSON response into answer text and suggestions."""
        try:
            data = json.loads(raw)
            answer = data.get("answer", raw)
            raw_suggestions = data.get("suggestions", [])
            suggestions = [
                SuggestionItem(
                    label=s.get("label", "")[:40],
                    message=s.get("message", s.get("label", "")),
                )
                for s in raw_suggestions
                if isinstance(s, dict) and s.get("label")
            ][:4]  # cap at 4
            return answer, suggestions if suggestions else None
        except (json.JSONDecodeError, AttributeError):
            logger.warning("llm_client.json_parse_failed", raw=raw[:200])
            return raw, None

    async def generate_stream(
        self,
        system_prompt: str,
        user_message: str,
        history: list[dict],
        tool_result_summary: str,
        tool_name: str,
    ) -> AsyncIterator[str]:
        """
        Streaming version of generate().

        LLM outputs JSON: {"answer": "...", "suggestions": [...]}
        This method streams only the answer text to the caller.
        After iteration completes, call .stream_suggestions on the
        returned object to get parsed suggestions.

        We use the same JSON instruction as generate() so the LLM
        produces suggestions in a single call — zero extra cost.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user",    "content": user_message},
            {
                "role": "assistant",
                "content": f"[Tool: {tool_name}]\n[Result]: {tool_result_summary}",
            },
            {
                "role": "user",
                "content": prompts()["inline"]["generate_json_instruction"],
            },
        ]
        stream = await self._call(
            messages=messages,
            model=_model(),
            stream=True,
        )

        # LLM outputs: {"answer": "...", "suggestions": [...]}
        # We stream ONLY the answer value content to the caller.
        # After stream ends, parse_stream_suggestions() returns suggestions.
        #
        # State machine:
        #   PREAMBLE  → accumulating {"answer": " prefix (not yielded)
        #   ANSWER    → inside the answer string value (yielded to caller)
        #   DONE      → past the closing quote (not yielded)

        full_json = ""
        state = "PREAMBLE"
        escape_next = False
        answer_start_idx = -1

        async for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta or not delta.content:
                continue

            full_json += delta.content

            if state == "DONE":
                continue

            if state == "PREAMBLE":
                # Look for the pattern "answer": " (with flexible whitespace)
                import re as _re
                m = _re.search(r'"answer"\s*:\s*"', full_json)
                if not m:
                    continue
                answer_start_idx = m.end()
                state = "ANSWER"
                # Yield any answer content already accumulated after the quote
                tail = full_json[answer_start_idx:]
                to_yield = []
                for ch in tail:
                    if escape_next:
                        escape_next = False
                        to_yield.append(ch)
                    elif ch == "\\":
                        escape_next = True
                        to_yield.append(ch)
                    elif ch == '"':
                        state = "DONE"
                        break
                    else:
                        to_yield.append(ch)
                if to_yield:
                    yield "".join(to_yield)
                continue

            # state == "ANSWER" — process each character of delta.content
            to_yield = []
            for ch in delta.content:
                if escape_next:
                    escape_next = False
                    to_yield.append(ch)
                elif ch == "\\":
                    escape_next = True
                    to_yield.append(ch)
                elif ch == '"':
                    state = "DONE"
                    break
                else:
                    to_yield.append(ch)
            if to_yield:
                yield "".join(to_yield)

        # Store full JSON for suggestion parsing
        self._last_stream_json = full_json

    def parse_stream_suggestions(self) -> list[SuggestionItem]:
        """Parse suggestions from the last generate_stream() call."""
        raw = getattr(self, "_last_stream_json", "")
        if not raw:
            return []
        try:
            data = json.loads(raw)
            raw_suggestions = data.get("suggestions", [])
            return [
                SuggestionItem(
                    label=s.get("label", "")[:40],
                    message=s.get("message", s.get("label", "")),
                )
                for s in raw_suggestions
                if isinstance(s, dict) and s.get("label")
            ][:4]
        except (json.JSONDecodeError, AttributeError):
            logger.debug("llm_client.stream_suggestions_parse_failed", raw=raw[:200])
            return []

    async def summarise(self, transcript: str) -> str:
        """
        Compress a conversation into a short summary paragraph.
        Uses the fallback (cheap) model — no need for GPT-4o here.
        """
        response = await self._call(
            messages=[
                {
                    "role": "system",
                    "content": prompts()["inline"]["summarise"],
                },
                {"role": "user", "content": transcript},
            ],
            model=_model(fallback=True),
        )
        return response.choices[0].message.content or ""
