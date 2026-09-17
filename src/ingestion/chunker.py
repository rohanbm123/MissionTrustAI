"""Paragraph-aware text chunking.

Splits on blank lines first so that a chunk rarely straddles a section header,
then packs paragraphs up to `chunk_size` characters with a trailing overlap so
facts near a boundary stay retrievable from both sides.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from src.config.settings import get_settings

_WHITESPACE = re.compile(r"[ \t]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")

# Presentation furniture that carries no case evidence: the demonstration-data
# banner and the "====" rule under each document title. Left in, these become
# retrievable passages and surface as meaningless "supporting evidence".
_BOILERPLATE = (
    re.compile(r"^FICTIONAL DEMONSTRATION DATA.*$", re.MULTILINE),
    re.compile(r"^[=\-]{3,}$", re.MULTILINE),
)


@dataclass
class Chunk:
    index: int
    content: str
    start_char: int
    end_char: int


def strip_boilerplate(text: str) -> str:
    """Remove banner and rule lines before a document is indexed."""
    for pattern in _BOILERPLATE:
        text = pattern.sub("", text)
    return text


def clean_text(text: str) -> str:
    """Normalise whitespace without destroying paragraph structure."""
    text = strip_boilerplate(text.replace("\r\n", "\n").replace("\r", "\n"))
    text = _WHITESPACE.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)
    return text.strip()


def split_paragraphs(text: str) -> List[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def chunk_text(
    text: str,
    chunk_size: int = None,
    chunk_overlap: int = None,
) -> List[Chunk]:
    """Pack paragraphs into overlapping chunks of roughly `chunk_size` chars."""
    settings = get_settings()
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap if chunk_overlap is not None else settings.chunk_overlap
    if chunk_overlap >= chunk_size:
        chunk_overlap = max(0, chunk_size // 4)

    cleaned = clean_text(text)
    if not cleaned:
        return []

    paragraphs = split_paragraphs(cleaned)
    chunks: List[Chunk] = []
    buffer = ""
    cursor = 0

    def flush(buf: str, start: int) -> None:
        if buf.strip():
            chunks.append(
                Chunk(
                    index=len(chunks),
                    content=buf.strip(),
                    start_char=start,
                    end_char=start + len(buf.strip()),
                )
            )

    start_char = 0
    for paragraph in paragraphs:
        # A single oversized paragraph is hard-split on sentence boundaries.
        if len(paragraph) > chunk_size:
            if buffer:
                flush(buffer, start_char)
                buffer = ""
            for piece in _split_long(paragraph, chunk_size):
                flush(piece, cursor)
                cursor += len(piece)
            start_char = cursor
            continue

        candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
        if len(candidate) <= chunk_size:
            buffer = candidate
        else:
            flush(buffer, start_char)
            tail = buffer[-chunk_overlap:] if chunk_overlap else ""
            cursor += max(0, len(buffer) - len(tail))
            start_char = cursor
            buffer = f"{tail}\n\n{paragraph}".strip() if tail else paragraph

    flush(buffer, start_char)
    return chunks


def _split_long(paragraph: str, chunk_size: int) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+", paragraph)
    pieces: List[str] = []
    buf = ""
    for sentence in sentences:
        if len(buf) + len(sentence) + 1 <= chunk_size:
            buf = f"{buf} {sentence}".strip()
        else:
            if buf:
                pieces.append(buf)
            buf = sentence[:chunk_size]
    if buf:
        pieces.append(buf)
    return pieces
