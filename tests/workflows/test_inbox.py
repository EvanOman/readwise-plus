"""Tests for ReadingInbox workflow."""

from datetime import UTC, datetime, timedelta

import httpx
import respx

from readwise_sdk.client import READWISE_API_V3_BASE, ReadwiseClient
from readwise_sdk.v3.models import DocumentCategory
from readwise_sdk.workflows.inbox import (
    ReadingInbox,
    create_category_rule,
    create_domain_rule,
    create_old_item_rule,
    create_title_pattern_rule,
)


class TestArchiveRules:
    """Tests for archive rule creation."""

    def test_create_old_item_rule(self) -> None:
        """Test creating old item rule."""
        from readwise_sdk.v3.models import Document

        rule = create_old_item_rule(30)
        assert rule.name == "older_than_30_days"

        old_doc = Document(
            id="1",
            url="https://example.com",
            created_at=datetime.now(UTC) - timedelta(days=60),
        )
        new_doc = Document(
            id="2",
            url="https://example.com",
            created_at=datetime.now(UTC) - timedelta(days=10),
        )

        assert rule.condition(old_doc) is True
        assert rule.condition(new_doc) is False

    def test_create_category_rule(self) -> None:
        """Test creating category rule."""
        from readwise_sdk.v3.models import Document

        rule = create_category_rule(DocumentCategory.TWEET)
        assert rule.name == "category_tweet"

        tweet_doc = Document(
            id="1",
            url="https://twitter.com/test",
            category=DocumentCategory.TWEET,
        )
        article_doc = Document(
            id="2",
            url="https://example.com",
            category=DocumentCategory.ARTICLE,
        )

        assert rule.condition(tweet_doc) is True
        assert rule.condition(article_doc) is False

    def test_create_title_pattern_rule(self) -> None:
        """Test creating title pattern rule."""
        from readwise_sdk.v3.models import Document

        rule = create_title_pattern_rule(r"newsletter", "newsletters")
        assert rule.name == "newsletters"

        newsletter_doc = Document(
            id="1",
            url="https://example.com",
            title="Weekly Newsletter: Tech Updates",
        )
        article_doc = Document(
            id="2",
            url="https://example.com",
            title="How to Code Better",
        )

        assert rule.condition(newsletter_doc) is True
        assert rule.condition(article_doc) is False

    def test_create_domain_rule(self) -> None:
        """Test creating domain rule."""
        from readwise_sdk.v3.models import Document

        rule = create_domain_rule("twitter.com")
        assert rule.name == "domain_twitter.com"

        twitter_doc = Document(id="1", url="https://twitter.com/user/status/123")
        other_doc = Document(id="2", url="https://example.com/article")

        assert rule.condition(twitter_doc) is True
        assert rule.condition(other_doc) is False


class TestReadingInbox:
    """Tests for ReadingInbox."""

    @respx.mock
    def test_get_queue_stats(self, api_key: str) -> None:
        """Test getting queue statistics."""
        now = datetime.now(UTC)

        def mock_response(request: httpx.Request) -> httpx.Response:
            url = str(request.url)
            if "location=new" in url:
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "id": "doc1",
                                "url": "https://a.com",
                                "category": "article",
                                "created_at": (now - timedelta(days=10)).isoformat(),
                            },
                            {
                                "id": "doc2",
                                "url": "https://b.com",
                                "category": "article",
                                "created_at": (now - timedelta(days=45)).isoformat(),
                            },
                        ],
                        "nextPageCursor": None,
                    },
                )
            elif "location=later" in url:
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            {
                                "id": "doc3",
                                "url": "https://c.com",
                                "category": "pdf",
                                "created_at": (now - timedelta(days=5)).isoformat(),
                            }
                        ],
                        "nextPageCursor": None,
                    },
                )
            else:
                return httpx.Response(200, json={"results": [], "nextPageCursor": None})

        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(side_effect=mock_response)

        client = ReadwiseClient(api_key=api_key)
        inbox = ReadingInbox(client)
        stats = inbox.get_queue_stats()

        assert stats.inbox_count == 2
        assert stats.reading_list_count == 1
        assert stats.total_unread == 3
        assert stats.items_older_than_30_days == 1
        assert stats.by_category["article"] == 2
        assert stats.by_category["pdf"] == 1

    @respx.mock
    def test_smart_archive_dry_run(self, api_key: str) -> None:
        """Test smart archive in dry run mode."""
        now = datetime.now(UTC)

        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "doc1",
                            "url": "https://twitter.com/test",
                            "title": "Tweet",
                            "category": "tweet",
                            "created_at": now.isoformat(),
                        },
                        {
                            "id": "doc2",
                            "url": "https://example.com",
                            "title": "Article",
                            "category": "article",
                            "created_at": now.isoformat(),
                        },
                    ],
                    "nextPageCursor": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        inbox = ReadingInbox(client)
        inbox.add_archive_rule(create_category_rule(DocumentCategory.TWEET))

        actions = inbox.smart_archive(dry_run=True)

        assert len(actions) == 1
        assert actions[0].document_id == "doc1"
        assert actions[0].action == "archive"

    @respx.mock
    def test_get_stale_items(self, api_key: str) -> None:
        """Test getting stale items."""
        now = datetime.now(UTC)

        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "doc1",
                            "url": "https://a.com",
                            "created_at": (now - timedelta(days=60)).isoformat(),
                        },
                        {
                            "id": "doc2",
                            "url": "https://b.com",
                            "created_at": (now - timedelta(days=10)).isoformat(),
                        },
                    ],
                    "nextPageCursor": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        inbox = ReadingInbox(client)

        stale = inbox.get_stale_items(days=30)

        assert len(stale) == 1
        assert stale[0].id == "doc1"

    @respx.mock
    def test_search_inbox(self, api_key: str) -> None:
        """Test searching inbox."""
        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "doc1", "url": "https://a.com", "title": "Python Tutorial"},
                        {"id": "doc2", "url": "https://b.com", "title": "JavaScript Guide"},
                    ],
                    "nextPageCursor": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        inbox = ReadingInbox(client)

        results = inbox.search_inbox("python")

        assert len(results) == 1
        assert results[0].id == "doc1"

    @respx.mock
    def test_get_inbox_by_priority(self, api_key: str) -> None:
        """Test getting inbox sorted by priority."""
        now = datetime.now(UTC)

        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "doc1",
                            "url": "https://a.com",
                            "title": "Old PDF",
                            "category": "pdf",
                            "created_at": (now - timedelta(days=30)).isoformat(),
                        },
                        {
                            "id": "doc2",
                            "url": "https://b.com",
                            "title": "New Article",
                            "category": "article",
                            "created_at": now.isoformat(),
                        },
                    ],
                    "nextPageCursor": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        inbox = ReadingInbox(client)

        prioritized = inbox.get_inbox_by_priority()

        # Article should come before PDF (higher priority category)
        assert prioritized[0].id == "doc2"
        assert prioritized[1].id == "doc1"

    @respx.mock
    def test_get_inbox_categories(self, api_key: str) -> None:
        """Test getting inbox grouped by category."""
        respx.get(f"{READWISE_API_V3_BASE}/list/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": "doc1", "url": "https://a.com", "category": "article"},
                        {"id": "doc2", "url": "https://b.com", "category": "article"},
                        {"id": "doc3", "url": "https://c.com", "category": "pdf"},
                    ],
                    "nextPageCursor": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        inbox = ReadingInbox(client)

        categories = inbox.get_inbox_categories()

        assert len(categories[DocumentCategory.ARTICLE]) == 2
        assert len(categories[DocumentCategory.PDF]) == 1

    def test_add_remove_archive_rules(self, api_key: str) -> None:
        """Test adding and removing archive rules."""
        client = ReadwiseClient(api_key=api_key)
        inbox = ReadingInbox(client)

        rule = create_old_item_rule(30)
        inbox.add_archive_rule(rule)

        assert len(inbox.get_archive_rules()) == 1

        removed = inbox.remove_archive_rule("older_than_30_days")
        assert removed is True
        assert len(inbox.get_archive_rules()) == 0

        # Try removing non-existent rule
        removed = inbox.remove_archive_rule("non_existent")
        assert removed is False

    @respx.mock
    def test_move_to_reading_list(self, api_key: str) -> None:
        """Test moving documents to reading list."""
        respx.patch(url__startswith=f"{READWISE_API_V3_BASE}/update/").mock(
            return_value=httpx.Response(200, json={"id": "doc1", "url": "https://example.com"})
        )

        client = ReadwiseClient(api_key=api_key)
        inbox = ReadingInbox(client)

        results = inbox.move_to_reading_list(["doc1", "doc2"])

        assert results["doc1"] is True
        assert results["doc2"] is True
