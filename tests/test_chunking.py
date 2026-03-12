"""Tests for Markdown-aware text chunking."""

from backend.indexer.chunking import Chunk, chunk_markdown


class TestChunkMarkdownBasic:
    def test_empty_text_returns_no_chunks(self):
        assert chunk_markdown("") == []
        assert chunk_markdown("   ") == []
        assert chunk_markdown("\n\n") == []

    def test_short_text_single_chunk(self):
        text = "Hello world. This is a simple paragraph."
        chunks = chunk_markdown(text)
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].chunk_index == 0

    def test_chunk_index_assigned_sequentially(self):
        # Build text large enough to produce multiple chunks
        text = "# Section 1\n\n" + "Word " * 500 + "\n\n# Section 2\n\n" + "Word " * 500
        chunks = chunk_markdown(text, chunk_size=500)
        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))

    def test_invalid_chunk_size_raises(self):
        try:
            chunk_markdown("hello", chunk_size=100, overlap=200)
            assert False, "Should have raised ValueError"
        except ValueError:
            pass


class TestHeadingTracking:
    def test_heading_path_tracked(self):
        text = "# Top\n\nSome intro text.\n\n## Sub\n\nSub section content."
        chunks = chunk_markdown(text, chunk_size=5000)
        # The first chunk should have ["# Top"]
        assert chunks[0].heading_path == ["# Top"]
        # The sub section should have ["# Top", "## Sub"]
        sub_chunks = [c for c in chunks if "## Sub" in c.heading_path]
        assert len(sub_chunks) > 0
        assert sub_chunks[0].heading_path == ["# Top", "## Sub"]

    def test_heading_path_resets_at_same_level(self):
        text = "# A\n\nContent A.\n\n# B\n\nContent B."
        chunks = chunk_markdown(text, chunk_size=5000)
        assert chunks[0].heading_path == ["# A"]
        assert chunks[1].heading_path == ["# B"]

    def test_nested_headings(self):
        text = "# H1\n\n## H2\n\n### H3\n\nDeep content.\n\n## H2b\n\nBack up."
        chunks = chunk_markdown(text, chunk_size=5000)
        # Find the chunk with H3 content
        h3_chunks = [c for c in chunks if "### H3" in c.heading_path]
        assert len(h3_chunks) > 0
        assert h3_chunks[0].heading_path == ["# H1", "## H2", "### H3"]

        # H2b should reset from H3
        h2b_chunks = [c for c in chunks if "## H2b" in c.heading_path]
        assert len(h2b_chunks) > 0
        assert h2b_chunks[0].heading_path == ["# H1", "## H2b"]


class TestCodeBlockPreservation:
    def test_code_block_kept_atomic(self):
        code = "```python\ndef foo():\n    return 42\n```"
        text = f"# Code\n\n{code}\n\nMore text after."
        chunks = chunk_markdown(text, chunk_size=5000)
        # Code block should be entirely within one chunk
        code_chunks = [c for c in chunks if "def foo():" in c.text]
        assert len(code_chunks) == 1
        assert "```python" in code_chunks[0].text
        assert "```" in code_chunks[0].text

    def test_heading_inside_code_block_ignored(self):
        text = "# Real heading\n\n```\n# Not a heading\n```\n\nAfter code."
        chunks = chunk_markdown(text, chunk_size=5000)
        # "# Not a heading" should not create a separate section
        # It should be inside the code block chunk
        for c in chunks:
            if "# Not a heading" in c.text:
                assert "```" in c.text


class TestTablePreservation:
    def test_table_kept_atomic(self):
        table = "| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |"
        text = f"# Data\n\n{table}\n\nAfter table."
        chunks = chunk_markdown(text, chunk_size=5000)
        table_chunks = [c for c in chunks if "| A | B |" in c.text]
        assert len(table_chunks) == 1
        assert "| 3 | 4 |" in table_chunks[0].text


class TestLargeDocumentSplitting:
    def test_large_section_split_into_multiple_chunks(self):
        # Create a large section that exceeds chunk_size
        sentences = [f"Sentence number {i} is here." for i in range(100)]
        text = "# Big Section\n\n" + " ".join(sentences)
        chunks = chunk_markdown(text, chunk_size=200, overlap=50)
        assert len(chunks) > 1

    def test_overlap_between_chunks(self):
        # Create content that will split with overlap
        sentences = [f"Unique sentence {i} with extra words." for i in range(50)]
        text = " ".join(sentences)
        chunks = chunk_markdown(text, chunk_size=200, overlap=50)
        if len(chunks) >= 2:
            # Some content from end of chunk N should appear in chunk N+1
            words_in_first = set(chunks[0].text.split())
            words_in_second = set(chunks[1].text.split())
            overlap_words = words_in_first & words_in_second
            assert len(overlap_words) > 0

    def test_line_numbers_tracked(self):
        text = "Line 1\nLine 2\nLine 3\n# Heading\nLine 5\nLine 6"
        chunks = chunk_markdown(text, chunk_size=5000)
        for chunk in chunks:
            assert chunk.start_line >= 1
            assert chunk.end_line >= chunk.start_line


class TestBase64Handling:
    def test_base64_excluded_from_length(self):
        # A base64 image shouldn't inflate the text length for splitting
        base64_img = "data:image/png;base64," + "A" * 5000
        text = f"# Section\n\nSome text with image: ![img]({base64_img})\n\nMore text."
        chunks = chunk_markdown(text, chunk_size=500)
        # Should still be one chunk because the base64 is excluded from length
        assert len(chunks) == 1


class TestChunkDataclass:
    def test_chunk_defaults(self):
        c = Chunk(text="hello")
        assert c.text == "hello"
        assert c.heading_path == []
        assert c.start_line == 0
        assert c.end_line == 0
        assert c.chunk_index == 0

    def test_chunk_with_values(self):
        c = Chunk(
            text="content",
            heading_path=["# H1", "## H2"],
            start_line=5,
            end_line=10,
            chunk_index=3,
        )
        assert c.heading_path == ["# H1", "## H2"]
        assert c.start_line == 5
        assert c.end_line == 10
        assert c.chunk_index == 3
