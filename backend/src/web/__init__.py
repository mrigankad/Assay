"""
Web research: search, fetch, snapshot, and turn pages into numbered evidence.

Modes (WEB_MODE):
  off   never touch the web (default)
  ask   only when the asker ticks "Use the web" for that question
  auto  also when the documents return nothing relevant

Search backends, first configured wins: TAVILY_API_KEY, BRAVE_API_KEY,
EXA_API_KEY, SEARXNG_URL (self-hosted). Pages are fetched read-only: GET
requests only, robots.txt respected, WEB_ALLOWED_DOMAINS / WEB_BLOCKED_DOMAINS
honoured, no forms, no logins, no cookies kept. Page text is treated as data:
it is quoted into the evidence, never followed as instructions. Every page used
is saved as a snapshot (url, time, title, text) so the citation can be checked
after the site changes.
"""

from .core import WebPassage, research, web_available, web_mode

__all__ = ["WebPassage", "research", "web_available", "web_mode"]
