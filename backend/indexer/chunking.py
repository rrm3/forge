"""Text chunking with Markdown structure awareness.

Splits text into overlapping chunks suitable for embedding and semantic search.
The Markdown-aware chunker preserves heading hierarchy, tables, and code blocks.
Falls back to sentence-boundary splitting for plain text sections.
"""

import re
from dataclasses import dataclass, field


@dataclass
class Chunk:
    """A chunk of text with structural metadata from the source document."""

    text: str
    heading_path: list[str] = field(default_factory=list)
    start_line: int = 0  # 1-based
    end_line: int = 0  # 1-based
    chunk_index: int = 0  # set by caller


# Pattern matching base64 data URIs (the large payload portion)
_BASE64_DATA_RE = re.compile(r"data:image/[^;]+;base64,[A-Za-z0-9+/=\s]+")

# Heading pattern
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def _text_length(text: str) -> int:
    """Compute text length excluding base64 data URI payloads."""
    return len(_BASE64_DATA_RE.sub("", text))


def chunk_markdown(
    text: str,
    chunk_size: int = 2000,
    overlap: int = 200,
) -> list[Chunk]:
    """Split Markdown text into chunks preserving document structure.

    Algorithm:
    1. Parse into sections by heading boundaries
    2. Track heading hierarchy (heading_path)
    3. Track line numbers relative to original text
    4. Emit small sections as single chunks
    5. Sub-split large sections preserving tables and code blocks as atomic units
    6. Apply overlap between consecutive chunks within a section

    Args:
        text: Markdown text to chunk
        chunk_size: Target size in characters (excluding base64 images)
        overlap: Characters of overlap between consecutive chunks

    Returns:
        List of Chunk objects with structural metadata
    """
    if chunk_size <= overlap:
        raise ValueError(f"chunk_size ({chunk_size}) must be greater than overlap ({overlap})")

    if not text or not text.strip():
        return []

    lines = text.split("\n")
    sections = _split_into_sections(lines)

    chunks: list[Chunk] = []
    heading_path: list[str] = []

    for section in sections:
        heading = section["heading"]
        section_lines = section["lines"]
        start_line = section["start_line"]

        # Update heading path based on current heading
        if heading:
            level = heading.count("#")
            heading_text = heading.strip()
            # Trim path to current level (replace deeper or same-level headings)
            heading_path = [h for h in heading_path if _heading_level(h) < level]
            heading_path.append(heading_text)

        section_text = "\n".join(section_lines)
        section_tlen = _text_length(section_text)

        if section_tlen == 0:
            continue

        if section_tlen <= chunk_size:
            chunks.append(
                Chunk(
                    text=section_text,
                    heading_path=list(heading_path),
                    start_line=start_line,
                    end_line=start_line + len(section_lines) - 1,
                )
            )
        else:
            # Sub-split large section
            sub_chunks = _split_large_section(
                section_lines, start_line, chunk_size, overlap, heading_path
            )
            chunks.extend(sub_chunks)

    # Set chunk_index
    for i, chunk in enumerate(chunks):
        chunk.chunk_index = i

    return chunks


def _heading_level(heading_text: str) -> int:
    """Extract heading level from a heading string like '## Foo'."""
    m = re.match(r"^(#{1,6})\s", heading_text)
    return len(m.group(1)) if m else 0


def _split_into_sections(lines: list[str]) -> list[dict]:
    """Split lines into sections based on heading boundaries.

    Returns list of dicts with keys: heading, lines, start_line
    """
    sections: list[dict] = []
    current_lines: list[str] = []
    current_heading: str | None = None
    current_start = 1  # 1-based

    for i, line in enumerate(lines):
        line_num = i + 1  # 1-based
        heading_match = _HEADING_RE.match(line)

        if heading_match and not _inside_code_block(lines, i):
            # Save previous section
            if current_lines or current_heading:
                sections.append(
                    {
                        "heading": current_heading,
                        "lines": current_lines,
                        "start_line": current_start,
                    }
                )

            current_heading = line
            current_lines = [line]
            current_start = line_num
        else:
            current_lines.append(line)

    # Final section
    if current_lines or current_heading:
        sections.append(
            {
                "heading": current_heading,
                "lines": current_lines,
                "start_line": current_start,
            }
        )

    return sections


def _inside_code_block(lines: list[str], index: int) -> bool:
    """Check if the line at index is inside a fenced code block."""
    fence_count = 0
    for i in range(index):
        if lines[i].strip().startswith("```"):
            fence_count += 1
    return fence_count % 2 == 1


def _split_large_section(
    lines: list[str],
    start_line: int,
    chunk_size: int,
    overlap: int,
    heading_path: list[str],
) -> list[Chunk]:
    """Sub-split a large section preserving tables and code blocks as atomic units."""
    blocks = _parse_blocks(lines, start_line)
    chunks: list[Chunk] = []

    current_blocks: list[dict] = []
    current_tlen = 0

    for block in blocks:
        block_tlen = _text_length(block["text"])

        if current_tlen + block_tlen > chunk_size and current_blocks:
            # Emit current chunk
            chunk = _blocks_to_chunk(current_blocks, heading_path)
            chunks.append(chunk)

            # Build overlap from end of current blocks
            current_blocks, current_tlen = _get_overlap_blocks(current_blocks, overlap)

        # If a single block exceeds chunk_size, split it by sentences
        if block_tlen > chunk_size and block["type"] == "prose":
            # Flush any accumulated blocks first
            if current_blocks:
                chunk = _blocks_to_chunk(current_blocks, heading_path)
                chunks.append(chunk)
                current_blocks = []
                current_tlen = 0

            sentence_chunks = _split_prose_block(block, chunk_size, overlap, heading_path)
            chunks.extend(sentence_chunks)
        else:
            current_blocks.append(block)
            current_tlen += block_tlen

    # Emit remaining
    if current_blocks:
        chunk = _blocks_to_chunk(current_blocks, heading_path)
        chunks.append(chunk)

    return chunks


def _parse_blocks(lines: list[str], start_line: int) -> list[dict]:
    """Parse lines into typed blocks: prose, table, code.

    Each block is a dict with keys: type, text, start_line, end_line
    """
    blocks: list[dict] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        line_num = start_line + i

        # Code block (fenced)
        if line.strip().startswith("```"):
            block_lines = [line]
            j = i + 1
            while j < len(lines):
                block_lines.append(lines[j])
                if lines[j].strip().startswith("```") and j > i:
                    j += 1
                    break
                j += 1
            blocks.append(
                {
                    "type": "code",
                    "text": "\n".join(block_lines),
                    "start_line": line_num,
                    "end_line": line_num + len(block_lines) - 1,
                }
            )
            i = j
            continue

        # Table (consecutive lines starting with |)
        if line.strip().startswith("|"):
            block_lines = []
            j = i
            while j < len(lines) and lines[j].strip().startswith("|"):
                block_lines.append(lines[j])
                j += 1
            blocks.append(
                {
                    "type": "table",
                    "text": "\n".join(block_lines),
                    "start_line": line_num,
                    "end_line": line_num + len(block_lines) - 1,
                }
            )
            i = j
            continue

        # Prose (everything else - collect consecutive non-special lines)
        block_lines = []
        j = i
        while j < len(lines):
            if lines[j].strip().startswith("```") or lines[j].strip().startswith("|"):
                break
            block_lines.append(lines[j])
            j += 1
        if block_lines:
            blocks.append(
                {
                    "type": "prose",
                    "text": "\n".join(block_lines),
                    "start_line": line_num,
                    "end_line": line_num + len(block_lines) - 1,
                }
            )
        i = j

    return blocks


def _blocks_to_chunk(blocks: list[dict], heading_path: list[str]) -> Chunk:
    """Combine blocks into a single Chunk."""
    text = "\n".join(b["text"] for b in blocks)
    return Chunk(
        text=text,
        heading_path=list(heading_path),
        start_line=blocks[0]["start_line"],
        end_line=blocks[-1]["end_line"],
    )


def _get_overlap_blocks(blocks: list[dict], target_overlap: int) -> tuple[list[dict], int]:
    """Get blocks from the end to achieve target overlap."""
    overlap_blocks: list[dict] = []
    overlap_length = 0

    for block in reversed(blocks):
        if overlap_length >= target_overlap:
            break
        overlap_blocks.insert(0, block)
        overlap_length += _text_length(block["text"])

    return overlap_blocks, overlap_length


def _split_prose_block(
    block: dict,
    chunk_size: int,
    overlap: int,
    heading_path: list[str],
) -> list[Chunk]:
    """Split a large prose block by sentence boundaries."""
    sentences = _split_sentences(block["text"])
    chunks: list[Chunk] = []

    current_sentences: list[str] = []
    current_length = 0

    for sentence in sentences:
        s_len = _text_length(sentence)

        if current_length + s_len > chunk_size and current_sentences:
            chunk_text_str = " ".join(current_sentences)
            chunks.append(
                Chunk(
                    text=chunk_text_str,
                    heading_path=list(heading_path),
                    start_line=block["start_line"],
                    end_line=block["end_line"],
                )
            )
            current_sentences, current_length = _get_overlap_start(current_sentences, overlap)

        current_sentences.append(sentence)
        current_length += s_len + 1

    if current_sentences:
        chunk_text_str = " ".join(current_sentences)
        if not chunks or chunk_text_str != chunks[-1].text:
            chunks.append(
                Chunk(
                    text=chunk_text_str,
                    heading_path=list(heading_path),
                    start_line=block["start_line"],
                    end_line=block["end_line"],
                )
            )

    return chunks


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences at sentence boundaries."""
    sentence_pattern = r"(?<=[.!?])\s+(?=[A-Z])|(?<=\n\n)"
    parts = re.split(sentence_pattern, text)
    return [p.strip() for p in parts if p.strip()]


def _get_overlap_start(sentences: list[str], target_overlap: int) -> tuple[list[str], int]:
    """Get sentences from the end to achieve target overlap."""
    overlap_sentences: list[str] = []
    overlap_length = 0

    for sentence in reversed(sentences):
        if overlap_length >= target_overlap:
            break
        overlap_sentences.insert(0, sentence)
        overlap_length += len(sentence) + 1

    return overlap_sentences, overlap_length
