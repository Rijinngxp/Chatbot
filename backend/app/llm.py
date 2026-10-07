"""LLM access shared by all agents. Each agent's provider (Groq cloud or local Ollama) and model come from .env.

Calls take the agent name ("planner", "verifier", "synthesizer") and resolve the provider + model via
Settings.agent_llm(), so switching an agent to Ollama is a one-line .env change.
"""
import json
import re
from collections.abc import AsyncIterator

from groq import AsyncGroq
from openai import AsyncOpenAI

from .config import get_settings

_clients: dict[str, AsyncGroq | AsyncOpenAI] = {}


def client(provider: str) -> AsyncGroq | AsyncOpenAI:
    if provider not in _clients:
        s = get_settings()
        if provider == "ollama":
            # Ollama serves an OpenAI-compatible API; it ignores the key but the SDK requires one.
            _clients[provider] = AsyncOpenAI(base_url=s.ollama_base_url, api_key="ollama", timeout=s.ollama_timeout)
        else:
            if not s.groq_api_key:
                raise RuntimeError("GROQ_API_KEY is not set. Add it to backend/.env (or set LLM_PROVIDER=ollama)")
            _clients[provider] = AsyncGroq(api_key=s.groq_api_key)
    return _clients[provider]


def _request(agent: str) -> tuple[AsyncGroq | AsyncOpenAI, dict]:
    """Client + base request params (model, provider-specific options) for an agent."""
    s = get_settings()
    provider, model = s.agent_llm(agent)
    params: dict = {"model": model}
    if provider == "ollama" and s.ollama_reasoning_effort:
        # Thinking models (qwen3) otherwise spend most of the time and token budget reasoning.
        params["reasoning_effort"] = s.ollama_reasoning_effort
    return client(provider), params


async def complete(agent: str, messages: list[dict], temperature: float, max_tokens: int) -> str:
    llm, params = _request(agent)
    resp = await llm.chat.completions.create(
        **params, messages=messages, temperature=temperature, max_tokens=max_tokens
    )
    return _strip_think(resp.choices[0].message.content or "")


async def stream(agent: str, messages: list[dict], temperature: float, max_tokens: int) -> AsyncIterator[str]:
    llm, params = _request(agent)
    resp = await llm.chat.completions.create(
        **params, messages=messages, temperature=temperature, max_tokens=max_tokens, stream=True
    )
    in_think = False
    async for chunk in resp:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if not delta:
            continue
        # Hide <think>...</think> blocks emitted by reasoning models (e.g. qwen3).
        if "<think>" in delta:
            in_think = True
            delta = delta.split("<think>", 1)[0]
        if in_think:
            if "</think>" not in delta:
                continue
            in_think = False
            delta = delta.split("</think>", 1)[1]
        if delta:
            yield delta


async def complete_json(agent: str, messages: list[dict], temperature: float, max_tokens: int) -> dict:
    """Ask for a JSON object; falls back to extracting the first {...} block if JSON mode is unsupported."""
    llm, params = _request(agent)
    try:
        resp = await llm.chat.completions.create(
            **params,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content or ""
    except Exception:
        text = await complete(agent, messages, temperature, max_tokens)
    return _parse_json(_strip_think(text))


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def _parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise
