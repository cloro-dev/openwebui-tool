"""Tests for cloro_tool.py. HTTP is stubbed.

The inline payloads follow the shape of live cloro responses. Set
CLORO_CAPTURE_DIR to a folder of saved responses (google.json, chatgpt.json,
aimode.json, gemini.json, badkey.json) to also parse those files.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cloro_tool  # noqa: E402

GOOGLE = {
    "success": True,
    "result": {
        "organicResults": [
            {
                "position": 1,
                "title": "Best rank trackers",
                "link": "https://example.com/rank-trackers/",
                "snippet": "A list.",
            },
            {"position": 2, "title": "Redirect only", "link": "https://www.google.com/goto?url=CAESZw"},
            {"position": 3, "title": "Empty link", "link": ""},
            {"position": 4, "title": "Other", "link": "https://example.org/page"},
        ],
        "peopleAlsoAsk": [{"question": "What is the best rank tracker?", "type": "AIOVERVIEW"}],
        "relatedSearches": [],
        "aioverview": {
            "text": "The best rank tracker tools cater to different needs.",
            "sources": [
                {"position": 1, "label": "Best rank trackers", "url": "https://example.com/rank-trackers/"},
                {"position": 2, "label": "Redirect", "url": "https://www.google.com/goto?url=abc"},
            ],
            "citationPills": [],
        },
    },
}

BING = {
    "success": True,
    "result": {
        "organicResults": [
            {
                "position": 1,
                "title": "Best rank trackers",
                "link": "https://example.com/rank-trackers/",
                "displayedLink": "https://example.com › rank-trackers",
                "snippet": "A list.",
                "page": 1,
            },
            {"position": 2, "title": "Empty link", "link": "", "page": 1},
            {"position": 3, "title": "Other", "link": "https://example.org/page", "page": 1},
        ],
        "aioverview": {
            "text": "Popular rank trackers include Semrush and Ahrefs.",
            "sources": [
                {
                    "position": 1,
                    "label": "Best rank trackers",
                    "url": "https://example.com/rank-trackers/",
                    "description": None,
                },
            ],
        },
    },
}

CHATGPT = {
    "success": True,
    "result": {
        "model": None,
        "text": "Plain answer.",
        "markdown": "**Markdown** answer.",
        "sources": [
            {"position": 1, "label": "Website and pricing", "url": "https://example.com/pricing", "footnote": True},
            {"position": 2, "label": "Docs", "url": "https://example.org/docs", "footnote": False},
        ],
        "citationPills": [],
    },
}

NO_SOURCES = {"success": True, "result": {"text": "An answer with no sources.", "sources": [], "citationPills": []}}

BAD_KEY = {"success": False, "error": {"code": "INVALID_API_KEY_FORMAT", "message": "Invalid API key format"}}


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def stub_http(monkeypatch, payload, status_code=200):
    calls = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None, headers=None):
            calls.append({"url": url, "json": json, "headers": headers})
            return FakeResponse(status_code, payload)

    monkeypatch.setattr(cloro_tool.httpx, "AsyncClient", FakeClient)
    return calls


def make_tool(api_key="test-key", country="US"):
    tool = cloro_tool.Tools()
    tool.valves = tool.Valves(api_key=api_key, country=country)
    return tool


class Recorder:
    def __init__(self):
        self.events = []

    async def __call__(self, event):
        self.events.append(event)

    def citations(self):
        return [e["data"] for e in self.events if e["type"] == "citation"]


def run(coro):
    return asyncio.run(coro)


def test_google_search_request_and_output(monkeypatch):
    calls = stub_http(monkeypatch, GOOGLE)
    emitter = Recorder()
    out = run(make_tool(country="DE").google_search("rank tracker", __event_emitter__=emitter))

    assert calls[0]["url"] == "https://api.cloro.dev/v1/monitor/google"
    assert calls[0]["json"] == {"query": "rank tracker", "country": "DE", "include": {"aioverview": True}}
    assert calls[0]["headers"] == {"Authorization": "Bearer test-key"}
    assert "AI Overview:" in out
    assert "[1] Best rank trackers - https://example.com/rank-trackers/" in out
    assert "goto" not in out
    assert "1. Best rank trackers - https://example.com/rank-trackers/" in out
    assert "4. Other - https://example.org/page" in out
    assert "What is the best rank tracker?" in out
    assert [c["source"]["url"] for c in emitter.citations()] == ["https://example.com/rank-trackers/"]


def test_google_search_without_ai_overview(monkeypatch):
    payload = {"success": True, "result": {"organicResults": GOOGLE["result"]["organicResults"]}}
    stub_http(monkeypatch, payload)
    out = run(make_tool().google_search("rank tracker"))
    assert "Google showed no AI Overview" in out


def test_bing_search_request_and_output(monkeypatch):
    calls = stub_http(monkeypatch, BING)
    emitter = Recorder()
    out = run(make_tool(country="DE").bing_search("rank tracker", country="gb", __event_emitter__=emitter))

    assert calls[0]["url"] == "https://api.cloro.dev/v1/monitor/bing"
    assert calls[0]["json"] == {"query": "rank tracker", "country": "GB", "include": {"aioverview": True}}
    assert out.startswith("AI Overview:\nPopular rank trackers include Semrush and Ahrefs.")
    assert "[1] Best rank trackers - https://example.com/rank-trackers/" in out
    assert "1. Best rank trackers - https://example.com/rank-trackers/" in out
    assert "Empty link" not in out
    assert "3. Other - https://example.org/page" in out
    assert "People also ask" not in out
    assert [c["source"]["url"] for c in emitter.citations()] == ["https://example.com/rank-trackers/"]


def test_bing_search_without_ai_overview(monkeypatch):
    payload = {"success": True, "result": {"organicResults": BING["result"]["organicResults"]}}
    stub_http(monkeypatch, payload)
    out = run(make_tool().bing_search("rank tracker"))
    assert out.startswith("Bing showed no AI Overview for this query.")


ADS = [
    {
        "position": 1,
        "blockPosition": "top",
        "type": "RESULT",
        "title": "Rank tracker sale",
        "url": "https://shop.example/rank",
        "page": 1,
        "description": "Track ranks.",
    },
    {
        "position": 1,
        "blockPosition": "rhs",
        "type": "SHOPPING_CARD",
        "title": "SEO book",
        "url": "https://www.google.com/goto?url=x",
        "price": {"value": 29, "currency": "$", "raw": "$29.00"},
        "store": "Shop",
    },
    {},
]


@pytest.mark.parametrize(("method", "payload"), [("google_search", GOOGLE), ("bing_search", BING)])
def test_search_lists_the_ads(monkeypatch, method, payload):
    payload = {"success": True, "result": {**payload["result"], "ads": ADS}}
    stub_http(monkeypatch, payload)
    emitter = Recorder()
    out = run(getattr(make_tool(), method)("rank tracker", __event_emitter__=emitter))

    assert (
        "\nAds:\n"
        "- [RESULT top 1] Rank tracker sale - https://shop.example/rank\n   Track ranks.\n"
        "- [SHOPPING_CARD rhs 1] SEO book\n   $29.00 | Shop\n"
        "- [] "
    ) in out
    assert [c["source"]["url"] for c in emitter.citations()] == ["https://example.com/rank-trackers/"]


def test_search_without_ads(monkeypatch):
    stub_http(monkeypatch, BING)
    assert "Ads:" not in run(make_tool().bing_search("rank tracker"))


@pytest.mark.parametrize(
    ("method", "engine", "label"),
    [
        ("ask_chatgpt", "chatgpt", "ChatGPT"),
        ("ask_google_ai_mode", "aimode", "Google AI Mode"),
        ("ask_gemini", "gemini", "Gemini"),
        ("ask_bing_ai_mode", "bing/aimode", "Bing AI Mode"),
    ],
)
def test_answer_tools(monkeypatch, method, engine, label):
    calls = stub_http(monkeypatch, CHATGPT)
    emitter = Recorder()
    out = run(getattr(make_tool(), method)("best rank tracker", country="gb", __event_emitter__=emitter))

    assert calls[0]["url"] == f"https://api.cloro.dev/v1/monitor/{engine}"
    assert calls[0]["json"] == {"prompt": "best rank tracker", "country": "GB", "include": {"markdown": True}}
    assert out.startswith(f"{label} answer:\n**Markdown** answer.")
    # Every source counts as cited, whatever the footnote flag says.
    assert "[2] Docs - https://example.org/docs" in out
    assert len(emitter.citations()) == 2
    statuses = [e["data"] for e in emitter.events if e["type"] == "status"]
    assert statuses[-1]["done"] is True


def test_google_search_links_are_dropped_from_sources(monkeypatch):
    payload = {
        "success": True,
        "result": {
            "text": "Answer.",
            "sources": [
                {"position": 1, "label": "Shopping", "url": "https://www.google.com/search?ibp=oshop&q=shoes"},
                {"position": 2, "label": "Shop", "url": "https://example.com/shoes"},
            ],
        },
    }
    stub_http(monkeypatch, payload)
    emitter = Recorder()
    out = run(make_tool().ask_google_ai_mode("q", __event_emitter__=emitter))
    assert "google.com/search" not in out
    assert [c["source"]["url"] for c in emitter.citations()] == ["https://example.com/shoes"]


def test_answer_without_sources_or_markdown(monkeypatch):
    stub_http(monkeypatch, NO_SOURCES)
    out = run(make_tool().ask_gemini("q"))
    assert "An answer with no sources." in out
    assert "Sources: none" in out


def test_error_body(monkeypatch):
    stub_http(monkeypatch, BAD_KEY, status_code=401)
    out = run(make_tool(api_key="bad").ask_chatgpt("q"))
    assert out == "cloro error (HTTP 401): INVALID_API_KEY_FORMAT Invalid API key format"


def test_missing_key_makes_no_request(monkeypatch):
    calls = stub_http(monkeypatch, CHATGPT)
    out = run(make_tool(api_key="").ask_chatgpt("q"))
    assert "API key is not set" in out
    assert calls == []


def test_public_methods_are_the_six_tools():
    names = sorted(
        n for n in dir(cloro_tool.Tools()) if not n.startswith("_") and callable(getattr(cloro_tool.Tools(), n))
    )
    assert names == [
        "Valves",
        "ask_bing_ai_mode",
        "ask_chatgpt",
        "ask_gemini",
        "ask_google_ai_mode",
        "bing_search",
        "google_search",
    ]


CAPTURES = os.environ.get("CLORO_CAPTURE_DIR")


@pytest.mark.skipif(not CAPTURES, reason="CLORO_CAPTURE_DIR not set")
@pytest.mark.parametrize(
    ("name", "method", "status"),
    [
        ("google", "google_search", 200),
        ("google-noaio", "google_search", 200),
        ("chatgpt", "ask_chatgpt", 200),
        ("aimode", "ask_google_ai_mode", 200),
        ("gemini", "ask_gemini", 200),
        ("aimode-md", "ask_google_ai_mode", 200),
        ("gemini-md", "ask_gemini", 200),
        ("chatgpt-noweb-md", "ask_chatgpt", 200),
        ("badkey", "ask_chatgpt", 401),
    ],
)
def test_live_captures(monkeypatch, name, method, status):
    payload = json.loads((Path(CAPTURES) / f"{name}.json").read_text())
    stub_http(monkeypatch, payload, status_code=status)
    emitter = Recorder()
    out = run(getattr(make_tool(), method)("q", __event_emitter__=emitter))

    if status != 200:
        assert out.startswith("cloro error (HTTP 401): INVALID_API_KEY_FORMAT")
        return
    result = payload["result"]
    sources = result.get("sources") or (result.get("aioverview") or {}).get("sources") or []
    expected = [s["url"] for s in sources if cloro_tool._is_usable(s.get("url") or "")]
    assert [c["source"]["url"] for c in emitter.citations()] == expected
    for url in expected:
        assert url in out
