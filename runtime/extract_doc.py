"""Text and links from an HTML page or an RSS/Atom feed.

This does not fetch, and it does not run anything in the document. A link
may be relative. The host joins it to the document base. This op does not
take that base. Script,
style, and template contents are left out of the text. ``javascript:``,
``data:``, ``vbscript:``, and ``file:`` links are dropped. ``HTML_TEXT`` is
still the tag stripper. This is the parser.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import Any, Dict, List

MAX_EXTRACT_BYTES = 1_000_000
MAX_LINKS = 1000
MAX_LINK_CHARS = 2000
_SKIP_TAGS = {"script", "style", "noscript", "template"}
_DROP_SCHEMES = ("javascript:", "data:", "vbscript:", "file:")


def _limit() -> Dict[str, Any]:
    return {
        "error": {
            "code": "EXTRACT_LIMIT",
            "message": "extract input exceeds 1000000 bytes",
        }
    }


def _parse_error() -> Dict[str, Any]:
    return {
        "error": {
            "code": "EXTRACT_PARSE",
            "message": "extract could not parse the document",
        }
    }


def _keep_link(href: str) -> bool:
    text = href.strip()
    if not text or len(text) > MAX_LINK_CHARS:
        return False
    lowered = text.lower()
    return not lowered.startswith(_DROP_SCHEMES)


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self.links: List[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: List[Any]) -> None:
        name = tag.lower()
        if not self._skip:
            self.parts.append(" ")
        if name in _SKIP_TAGS:
            self._skip += 1
        if self._skip:
            return
        found = {str(key).lower(): value for key, value in attrs}
        href = found.get("href")
        if not isinstance(href, str):
            return
        if name in {"a", "area"}:
            self._add(href)
        elif name == "link":
            rel = str(found.get("rel") or "").lower()
            if "stylesheet" not in rel:
                self._add(href)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in _SKIP_TAGS and self._skip:
            self._skip -= 1
        if not self._skip:
            self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._skip and data:
            self.parts.append(data)

    def _add(self, href: str) -> None:
        if len(self.links) >= MAX_LINKS or not _keep_link(href):
            return
        text = href.strip()
        if text not in self.links:
            self.links.append(text)


def _collapse(parts: List[str]) -> str:
    return " ".join("".join(parts).split())


def _html(raw: str) -> Dict[str, Any]:
    page = _Page()
    try:
        page.feed(raw)
        page.close()
    except Exception:
        return _parse_error()
    return {"text": _collapse(page.parts), "links": page.links}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _feed(raw: str) -> Dict[str, Any]:
    lowered = raw.lower()
    if "<!doctype" in lowered or "<!entity" in lowered:
        return _parse_error()
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return _parse_error()
    parts: List[str] = []
    links: List[str] = []

    def add_link(href: str) -> None:
        if len(links) >= MAX_LINKS or not _keep_link(href):
            return
        text = href.strip()
        if text not in links:
            links.append(text)

    for node in root.iter():
        name = _local(node.tag)
        if name == "link":
            href = node.attrib.get("href")
            if isinstance(href, str):
                add_link(href)
            elif node.text and node.text.strip():
                add_link(node.text)
        if name not in {"title", "description", "summary", "content"}:
            continue
        body = "".join(node.itertext()).strip()
        if not body:
            continue
        if "<" in body and ">" in body:
            inner = _html(body)
            if "error" in inner:
                continue
            if inner.get("text"):
                parts.append(str(inner["text"]))
            for href in inner.get("links") or []:
                add_link(str(href))
        else:
            parts.append(body)
    return {"text": _collapse(parts), "links": links}


def _kind_of(raw: str, kind: str) -> str:
    asked = (kind or "auto").strip().lower()
    if asked in {"html", "rss", "atom"}:
        return "html" if asked == "html" else "feed"
    if asked != "auto":
        return "bad"
    head = raw.lstrip()[:1000].lower()
    if head.startswith("<?xml") or head.startswith("<rss") or head.startswith("<feed"):
        return "feed"
    return "html"


def extract_document(value: Any, kind: Any = "auto") -> Any:
    """Return ``{text, links}`` or an error value that does not include the document."""
    raw = "" if value is None else str(value)
    if len(raw.encode("utf-8")) > MAX_EXTRACT_BYTES:
        return _limit()
    chosen = _kind_of(raw, "" if kind is None else str(kind))
    if chosen == "bad":
        return _parse_error()
    if chosen == "feed":
        return _feed(raw)
    return _html(raw)
