"""Tests for TagWorkflow."""

import httpx
import respx

from readwise_sdk.client import READWISE_API_V2_BASE, ReadwiseClient
from readwise_sdk.workflows.tags import TagPattern, TagWorkflow


class TestTagPattern:
    """Tests for TagPattern."""

    def test_pattern_matches_text(self) -> None:
        """Test pattern matching in text."""
        from readwise_sdk.v2.models import Highlight

        pattern = TagPattern(pattern=r"python", tag="programming")
        highlight = Highlight(id=1, text="I love Python programming")

        assert pattern.matches(highlight) is True

    def test_pattern_no_match(self) -> None:
        """Test pattern not matching."""
        from readwise_sdk.v2.models import Highlight

        pattern = TagPattern(pattern=r"rust", tag="programming")
        highlight = Highlight(id=1, text="I love Python programming")

        assert pattern.matches(highlight) is False

    def test_pattern_matches_note(self) -> None:
        """Test pattern matching in note."""
        from readwise_sdk.v2.models import Highlight

        pattern = TagPattern(pattern=r"important", tag="review", match_in_text=False)
        highlight = Highlight(id=1, text="Some text", note="This is important!")

        assert pattern.matches(highlight) is True

    def test_case_sensitive(self) -> None:
        """Test case-sensitive matching."""
        from readwise_sdk.v2.models import Highlight

        pattern = TagPattern(pattern=r"Python", tag="python", case_sensitive=True)
        highlight1 = Highlight(id=1, text="I love Python")
        highlight2 = Highlight(id=2, text="I love python")

        assert pattern.matches(highlight1) is True
        assert pattern.matches(highlight2) is False


class TestTagWorkflow:
    """Tests for TagWorkflow."""

    @respx.mock
    def test_auto_tag_highlights_dry_run(self, api_key: str) -> None:
        """Test auto-tagging in dry run mode."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "Python is great", "tags": []},
                        {"id": 2, "text": "JavaScript is also good", "tags": []},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        workflow = TagWorkflow(client)

        patterns = [
            TagPattern(pattern=r"python", tag="programming-python"),
            TagPattern(pattern=r"javascript", tag="programming-js"),
        ]

        results = workflow.auto_tag_highlights(patterns, dry_run=True)

        assert 1 in results
        assert "programming-python" in results[1]
        assert 2 in results
        assert "programming-js" in results[2]

    @respx.mock
    def test_auto_tag_skips_already_tagged(self, api_key: str) -> None:
        """Test that auto-tagging skips already tagged highlights."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": 1,
                            "text": "Python is great",
                            "tags": [{"id": 10, "name": "programming-python"}],
                        },
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        workflow = TagWorkflow(client)

        patterns = [TagPattern(pattern=r"python", tag="programming-python")]

        results = workflow.auto_tag_highlights(patterns, dry_run=True)

        assert len(results) == 0

    @respx.mock
    def test_get_tag_report(self, api_key: str) -> None:
        """Test getting tag report."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "Test 1", "tags": [{"id": 1, "name": "tag1"}]},
                        {"id": 2, "text": "Test 2", "tags": [{"id": 1, "name": "tag1"}]},
                        {"id": 3, "text": "Test 3", "tags": [{"id": 2, "name": "tag2"}]},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        workflow = TagWorkflow(client)

        report = workflow.get_tag_report()

        assert report.total_tags == 2
        assert report.total_usages == 3
        assert ("tag1", 2) in report.tags_by_usage
        assert ("tag2", 1) in report.tags_by_usage

    @respx.mock
    def test_get_highlights_by_tag(self, api_key: str) -> None:
        """Test getting highlights by tag."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "Test 1", "tags": [{"id": 1, "name": "important"}]},
                        {"id": 2, "text": "Test 2", "tags": []},
                        {"id": 3, "text": "Test 3", "tags": [{"id": 1, "name": "important"}]},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        workflow = TagWorkflow(client)

        results = workflow.get_highlights_by_tag("important")

        assert len(results) == 2
        assert results[0].id == 1
        assert results[1].id == 3

    @respx.mock
    def test_get_untagged_highlights(self, api_key: str) -> None:
        """Test getting untagged highlights."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "Test 1", "tags": [{"id": 1, "name": "tag1"}]},
                        {"id": 2, "text": "Test 2", "tags": []},
                        {"id": 3, "text": "Test 3"},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        workflow = TagWorkflow(client)

        results = workflow.get_untagged_highlights()

        assert len(results) == 2
        assert results[0].id == 2
        assert results[1].id == 3

    @respx.mock
    def test_merge_tags_dry_run(self, api_key: str) -> None:
        """Test merging tags in dry run mode."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "Test 1", "tags": [{"id": 1, "name": "Python"}]},
                        {"id": 2, "text": "Test 2", "tags": [{"id": 2, "name": "python"}]},
                        {"id": 3, "text": "Test 3", "tags": [{"id": 3, "name": "PYTHON"}]},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        workflow = TagWorkflow(client)

        affected = workflow.merge_tags(["Python", "python", "PYTHON"], "python", dry_run=True)

        assert len(affected) == 3

    @respx.mock
    def test_rename_tag_dry_run(self, api_key: str) -> None:
        """Test renaming tag in dry run mode."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "Test 1", "tags": [{"id": 1, "name": "old-name"}]},
                        {"id": 2, "text": "Test 2", "tags": []},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        workflow = TagWorkflow(client)

        affected = workflow.rename_tag("old-name", "new-name", dry_run=True)

        assert len(affected) == 1
        assert 1 in affected

    @respx.mock
    def test_delete_tag_dry_run(self, api_key: str) -> None:
        """Test deleting tag in dry run mode."""
        respx.get(f"{READWISE_API_V2_BASE}/highlights/").mock(
            return_value=httpx.Response(
                200,
                json={
                    "results": [
                        {"id": 1, "text": "Test 1", "tags": [{"id": 1, "name": "to-delete"}]},
                        {"id": 2, "text": "Test 2", "tags": [{"id": 1, "name": "to-delete"}]},
                    ],
                    "next": None,
                },
            )
        )

        client = ReadwiseClient(api_key=api_key)
        workflow = TagWorkflow(client)

        affected = workflow.delete_tag("to-delete", dry_run=True)

        assert len(affected) == 2
