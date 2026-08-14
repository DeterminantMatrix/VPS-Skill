#!/usr/bin/env python3
"""Fetch one bounded HTML document per domain and summarize its static footprint."""

from __future__ import annotations

import argparse
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser


PLACEHOLDER_MARKERS = (
    "domain is for sale",
    "this domain is for sale",
    "buy this domain",
    "coming soon",
    "under construction",
    "website under construction",
    "default web site page",
    "welcome to nginx",
    "apache2 debian default page",
    "parked free",
)


class FootprintParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.counts = {
            "links": 0,
            "images": 0,
            "scripts": 0,
            "stylesheets": 0,
            "headings": 0,
        }
        self._hidden_depth = 0
        self._in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        lowered = tag.lower()
        attributes = {str(key).lower(): str(value or "") for key, value in attrs}
        if lowered in {"script", "style", "noscript", "template"}:
            self._hidden_depth += 1
        if lowered == "a" and attributes.get("href"):
            self.counts["links"] += 1
        elif lowered == "img":
            self.counts["images"] += 1
        elif lowered == "script":
            self.counts["scripts"] += 1
        elif lowered == "link" and "stylesheet" in attributes.get("rel", "").lower():
            self.counts["stylesheets"] += 1
        elif lowered in {"h1", "h2"}:
            self.counts["headings"] += 1
        elif lowered == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript", "template"}:
            self._hidden_depth = max(0, self._hidden_depth - 1)
        elif lowered == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        cleaned = re.sub(r"\s+", " ", data).strip()
        if not cleaned:
            return
        if self._in_title:
            self.title_parts.append(cleaned)
        if self._hidden_depth == 0:
            self.text_parts.append(cleaned)


def normalize_domain(raw: str) -> str:
    value = raw.strip()
    if "://" not in value:
        value = "https://" + value
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError(f"expected HTTPS hostname: {raw}")
    return parsed.hostname.rstrip(".").lower()


def classify(text_chars: int, links: int, markers: list[str]) -> str:
    if markers:
        return "placeholder"
    if text_chars >= 1500 and links >= 10:
        return "substantial"
    if text_chars >= 300 and links >= 5:
        return "small-active"
    return "uncertain"


def inspect(domain: str, timeout: float, max_bytes: int) -> dict[str, object]:
    url = f"https://{domain}/"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; RealitySNISelector/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    context = ssl.create_default_context()

    def consume(response, status: int) -> dict[str, object]:
        raw = response.read(max_bytes + 1)
        truncated = len(raw) > max_bytes
        raw = raw[:max_bytes]
        content_type = response.headers.get("Content-Type", "")
        charset = response.headers.get_content_charset() or "utf-8"
        html = raw.decode(charset, errors="replace")
        parser = FootprintParser()
        parser.feed(html)
        text = " ".join(parser.text_parts)
        title = " ".join(parser.title_parts)
        haystack = (title + " " + text).lower()
        markers = [marker for marker in PLACEHOLDER_MARKERS if marker in haystack]
        return {
            "domain": domain,
            "requested_url": url,
            "final_url": response.geturl(),
            "status": status,
            "content_type": content_type,
            "document_bytes_read": len(raw),
            "document_truncated": truncated,
            "title": title[:300],
            "visible_text_chars": len(text),
            **parser.counts,
            "placeholder_markers": markers,
            "first_pass_classification": classify(
                len(text), parser.counts["links"], markers
            ),
            "browser_review_required": True,
        }

    try:
        with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
            return consume(response, response.status)
    except urllib.error.HTTPError as exc:
        # WAF and authenticated sites may return useful HTML with non-2xx status.
        return consume(exc, exc.code)
    except (urllib.error.URLError, TimeoutError, ssl.SSLError, OSError) as exc:
        return {
            "domain": domain,
            "requested_url": url,
            "error": f"{type(exc).__name__}: {exc}",
            "browser_review_required": True,
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch one bounded HTML document per SNI candidate."
    )
    parser.add_argument("domains", nargs="+")
    parser.add_argument("--timeout", type=float, default=12.0)
    parser.add_argument("--max-bytes", type=int, default=524288)
    args = parser.parse_args()
    if args.timeout <= 0 or not 4096 <= args.max_bytes <= 4 * 1024 * 1024:
        parser.error("timeout must be positive and max-bytes must be 4096..4194304")
    results = [
        inspect(normalize_domain(item), args.timeout, args.max_bytes)
        for item in args.domains
    ]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
