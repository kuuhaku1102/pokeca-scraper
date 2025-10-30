"""Utility for managing the WordPress ranking page.

This helper reads ranking entries from a local JSON file and pushes them to a
WordPress page via the REST API. The generated page content is composed of
Gutenberg blocks so that the ranking can be edited afterwards directly from the
WordPress管理画面 (dashboard) without touching the code.

Environment variables
---------------------
WP_RANKING_JSON
    Optional path to a JSON file. Defaults to ``ranking_data.json`` in the
    repository root.
WP_RANKING_SLUG
    The slug of the page to upsert. Defaults to ``ranking``.
WP_RANKING_TITLE
    Title of the page when a new one is created. Defaults to ``ランキング``.
WP_API_BASE
    Base REST API endpoint. Example: ``https://example.com/wp-json/wp/v2``.
WP_USER / WP_APP_PASS
    Credentials for the REST API.
"""

from __future__ import annotations

import html
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import requests


DEFAULT_JSON_PATH = Path("ranking_data.json")
DEFAULT_SLUG = "ranking"
DEFAULT_TITLE = "ランキング"


@dataclass
class RankingEntry:
    """Single row in the ranking list."""

    rank: int
    title: str
    image_url: str
    image_link: str
    description: str
    detail_url: str
    official_url: str

    @classmethod
    def from_dict(cls, data: dict) -> "RankingEntry":
        try:
            rank = int(data.get("rank"))
        except (TypeError, ValueError):
            raise ValueError(f"Invalid rank value: {data.get('rank')!r}") from None

        required_fields = [
            "title",
            "image_url",
            "image_link",
            "description",
            "detail_url",
            "official_url",
        ]
        missing = [field for field in required_fields if not data.get(field)]
        if missing:
            raise ValueError(f"Missing fields for rank {rank}: {', '.join(missing)}")

        return cls(
            rank=rank,
            title=str(data["title"]),
            image_url=str(data["image_url"]),
            image_link=str(data["image_link"]),
            description=str(data["description"]),
            detail_url=str(data["detail_url"]),
            official_url=str(data["official_url"]),
        )


def load_entries(path: Path) -> List[RankingEntry]:
    if not path.exists():
        raise FileNotFoundError(f"Ranking data file not found: {path}")
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        raise ValueError("Ranking data must be a JSON list")
    entries = [RankingEntry.from_dict(item) for item in raw]
    entries.sort(key=lambda item: item.rank)
    return entries


def build_block_content(entries: List[RankingEntry]) -> str:
    blocks: List[str] = []
    for entry in entries:
        title = html.escape(entry.title)
        description = html.escape(entry.description).replace("\n", "<br>")
        blocks.append(
            f"""
<!-- wp:group {{"className":"ranking-entry"}} -->
<div class="wp-block-group ranking-entry">
    <!-- wp:heading {{"level":3}} -->
    <h3 class="ranking-entry__title">第{entry.rank}位 {title}</h3>
    <!-- /wp:heading -->

    <!-- wp:columns -->
    <div class="wp-block-columns ranking-entry__body">
        <!-- wp:column {{"width":"30%"}} -->
        <div class="wp-block-column" style="flex-basis:30%">
            <!-- wp:image {{"sizeSlug":"full","linkDestination":"custom","href":"{html.escape(entry.image_link)}"}} -->
            <figure class="wp-block-image size-full ranking-entry__image">
                <a href="{html.escape(entry.image_link)}" target="_blank" rel="noreferrer noopener">
                    <img src="{html.escape(entry.image_url)}" alt="{title}" />
                </a>
            </figure>
            <!-- /wp:image -->
        </div>
        <!-- /wp:column -->

        <!-- wp:column -->
        <div class="wp-block-column">
            <!-- wp:paragraph -->
            <p class="ranking-entry__description">{description}</p>
            <!-- /wp:paragraph -->

            <!-- wp:buttons {{"layout":{{"type":"flex","justifyContent":"left"}}}} -->
            <div class="wp-block-buttons">
                <!-- wp:button {{"className":"is-style-outline ranking-entry__detail"}} -->
                <div class="wp-block-button is-style-outline ranking-entry__detail">
                    <a class="wp-block-button__link wp-element-button" href="{html.escape(entry.detail_url)}" target="_blank" rel="noreferrer noopener">詳細を見る</a>
                </div>
                <!-- /wp:button -->

                <!-- wp:button {{"className":"ranking-entry__official"}} -->
                <div class="wp-block-button ranking-entry__official">
                    <a class="wp-block-button__link wp-element-button" href="{html.escape(entry.official_url)}" target="_blank" rel="noreferrer noopener">公式サイトへ</a>
                </div>
                <!-- /wp:button -->
            </div>
            <!-- /wp:buttons -->
        </div>
        <!-- /wp:column -->
    </div>
    <!-- /wp:columns -->
</div>
<!-- /wp:group -->
""".strip()
        )

    intro_block = (
        "<!-- wp:paragraph -->\n"
        "<p class=\"ranking-intro\">管理画面から直接編集できるランキングです。</p>\n"
        "<!-- /wp:paragraph -->"
    )

    return "\n\n".join([intro_block, *blocks])


def _auth() -> tuple[str, str]:
    user = os.environ.get("WP_USER")
    password = os.environ.get("WP_APP_PASS")
    if not user or not password:
        raise RuntimeError("WP_USER and WP_APP_PASS must be set")
    return user, password


def _api_base() -> str:
    base = os.environ.get("WP_API_BASE")
    if not base:
        raise RuntimeError("WP_API_BASE environment variable is required")
    return base.rstrip("/")


def fetch_page_id(slug: str) -> Optional[int]:
    url = f"{_api_base()}/pages"
    res = requests.get(url, params={"slug": slug}, auth=_auth(), timeout=30)
    res.raise_for_status()
    payload = res.json()
    if payload:
        return int(payload[0]["id"])
    return None


def upsert_page(content: str, entries: List[RankingEntry], *, slug: str, title: str) -> None:
    data = {
        "title": title,
        "content": content,
        "status": "publish",
        "slug": slug,
        "meta": {"ranking_data": json.dumps([entry.__dict__ for entry in entries])},
    }
    page_id = fetch_page_id(slug)
    base = _api_base()

    if page_id:
        url = f"{base}/pages/{page_id}"
        response = requests.post(url, auth=_auth(), json=data, timeout=30)
        action = "updated"
    else:
        url = f"{base}/pages"
        response = requests.post(url, auth=_auth(), json=data, timeout=30)
        action = "created"

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:  # pragma: no cover - simple logging
        raise RuntimeError(f"Failed to upsert page ({response.status_code}): {response.text}") from exc

    print(f"✅ Ranking page {action}: {response.json().get('link')}")


def main() -> None:
    json_path = Path(os.environ.get("WP_RANKING_JSON", DEFAULT_JSON_PATH))
    slug = os.environ.get("WP_RANKING_SLUG", DEFAULT_SLUG)
    title = os.environ.get("WP_RANKING_TITLE", DEFAULT_TITLE)

    entries = load_entries(json_path)
    content = build_block_content(entries)
    upsert_page(content, entries, slug=slug, title=title)


if __name__ == "__main__":
    main()
