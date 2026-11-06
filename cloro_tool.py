"""
title: cloro: Google AI Overview, ChatGPT, AI Mode and Gemini answers
author: cloro
author_url: https://cloro.dev?utm_source=open-webui&utm_medium=byok
git_url: https://github.com/cloro-dev/openwebui-tool.git
description: Google results with the AI Overview, and the answers that ChatGPT, Google AI Mode and Gemini show to users, with their sources. Needs a cloro API key.
required_open_webui_version: 0.13.0
version: 0.1.0
license: MIT
"""

import httpx
from pydantic import BaseModel, Field

API_BASE = "https://api.cloro.dev/v1/monitor"


class Tools:
    class Valves(BaseModel):
        api_key: str = Field(
            default="",
            description="cloro API key. Get one at https://dashboard.cloro.dev/api-keys?utm_source=open-webui&utm_medium=byok",
        )
        country: str = Field(
            default="US",
            description="Default country for results, as an ISO 3166-1 alpha-2 code (for example US, GB, DE).",
        )

    def __init__(self):
        self.valves = self.Valves()

    async def google_search(self, query: str, country: str = "", __event_emitter__=None) -> str:
        """
        Search Google and return the organic results and the AI Overview, with the sources the AI Overview cites. Costs 7 cloro credits.
        :param query: The search query.
        :param country: Optional ISO 3166-1 alpha-2 country code. Leave empty to use the default.
        """
        result = await self._call(
            "google",
            {"query": query, "country": self._country(country), "include": {"aioverview": True}},
            f'Searching Google for "{query}"',
            __event_emitter__,
        )
        if isinstance(result, str):
            return result

        lines = []
        aio = result.get("aioverview")
        if isinstance(aio, dict) and aio.get("text"):
            sources = _usable_sources(aio.get("sources"))
            lines.append("AI Overview:")
            lines.append(aio["text"].strip())
            lines.extend(_format_sources(sources))
            await _emit_sources(__event_emitter__, sources)
        else:
            lines.append("Google showed no AI Overview for this query.")

        lines.append("")
        lines.append("Organic results:")
        for item in result.get("organicResults") or []:
            link = item.get("link") or ""
            if not _is_usable(link):
                continue
            lines.append(f"{item.get('position')}. {item.get('title', '')} - {link}")
            if item.get("snippet"):
                lines.append(f"   {item['snippet']}")

        questions = [q.get("question") for q in result.get("peopleAlsoAsk") or [] if q.get("question")]
        if questions:
            lines.append("")
            lines.append("People also ask:")
            lines.extend(f"- {q}" for q in questions)
        return "\n".join(lines)

    async def ask_chatgpt(self, prompt: str, country: str = "", __event_emitter__=None) -> str:
        """
        Send a prompt to the ChatGPT web app and return its answer and the sources it cites. Costs 7 cloro credits.
        :param prompt: The prompt to send.
        :param country: Optional ISO 3166-1 alpha-2 country code. Leave empty to use the default.
        """
        return await self._answer("chatgpt", "ChatGPT", prompt, country, __event_emitter__)

    async def ask_google_ai_mode(self, prompt: str, country: str = "", __event_emitter__=None) -> str:
        """
        Send a prompt to Google AI Mode and return its answer and the sources it cites. Costs 6 cloro credits.
        :param prompt: The prompt to send.
        :param country: Optional ISO 3166-1 alpha-2 country code. Leave empty to use the default.
        """
        return await self._answer("aimode", "Google AI Mode", prompt, country, __event_emitter__)

    async def ask_gemini(self, prompt: str, country: str = "", __event_emitter__=None) -> str:
        """
        Send a prompt to the Gemini web app and return its answer and the sources it cites. Costs 6 cloro credits.
        :param prompt: The prompt to send.
        :param country: Optional ISO 3166-1 alpha-2 country code. Leave empty to use the default.
        """
        return await self._answer("gemini", "Gemini", prompt, country, __event_emitter__)

    async def _answer(self, engine: str, label: str, prompt: str, country: str, emitter) -> str:
        result = await self._call(
            engine,
            {"prompt": prompt, "country": self._country(country), "include": {"markdown": True}},
            f"Asking {label}",
            emitter,
        )
        if isinstance(result, str):
            return result
        sources = _usable_sources(result.get("sources"))
        await _emit_sources(emitter, sources)
        answer = (result.get("markdown") or result.get("text") or "").strip()
        return "\n".join([f"{label} answer:", answer, *_format_sources(sources)])

    def _country(self, country: str) -> str:
        return (country or self.valves.country or "US").strip().upper()

    async def _call(self, engine: str, body: dict, status: str, emitter):
        """Return the `result` object, or an error string for the model."""
        if not self.valves.api_key:
            return "The cloro API key is not set. An admin must set it in the Valves of the cloro tool."

        await _emit_status(emitter, f"{status} through cloro", done=False)
        try:
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    f"{API_BASE}/{engine}",
                    json=body,
                    headers={"Authorization": f"Bearer {self.valves.api_key}"},
                )
            data = resp.json()
        except Exception as exc:
            await _emit_status(emitter, "cloro request failed", done=True)
            return f"cloro request failed: {exc}"

        if resp.status_code >= 400 or not data.get("success"):
            error = data.get("error") or {}
            await _emit_status(emitter, "cloro request failed", done=True)
            return f"cloro error (HTTP {resp.status_code}): {error.get('code', '')} {error.get('message', '')}".strip()

        await _emit_status(emitter, f"{status} through cloro: done", done=True)
        return data.get("result") or {}


def _is_usable(url: str) -> bool:
    """Skip empty links, Google redirect links (google.com/goto) and Google search links (google.com/search)."""
    path = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    return bool(url) and not path.endswith(("google.com/goto", "google.com/search"))


def _usable_sources(sources) -> list:
    return [s for s in sources or [] if isinstance(s, dict) and _is_usable(s.get("url") or "")]


def _format_sources(sources: list) -> list:
    if not sources:
        return ["", "Sources: none"]
    lines = ["", "Sources:"]
    for i, src in enumerate(sources, 1):
        lines.append(f"[{i}] {src.get('label') or src['url']} - {src['url']}")
    return lines


async def _emit_status(emitter, description: str, done: bool) -> None:
    if emitter:
        await emitter({"type": "status", "data": {"description": description, "done": done}})


async def _emit_sources(emitter, sources: list) -> None:
    if not emitter:
        return
    for src in sources:
        title = src.get("label") or src["url"]
        await emitter(
            {
                "type": "citation",
                "data": {
                    "document": [src.get("description") or title],
                    "metadata": [{"source": src["url"], "name": title}],
                    "source": {"name": title, "url": src["url"]},
                },
            }
        )
