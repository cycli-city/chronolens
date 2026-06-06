from typing import List
from dataclasses import dataclass


@dataclass
class Chunk:
    """A piece of a document with metadata."""
    text: str
    chunk_index: int
    char_start: int
    char_end: int


class TextChunker:
    """Splits text into overlapping chunks for embedding."""

    def __init__(self, chunk_size: int = 800, overlap: int = 150):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> List[Chunk]:
        """Split text into overlapping chunks."""
        if not text:
            return []

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(text):
            end = min(start + self.chunk_size, len(text))

            # Try to break at a sentence boundary
            if end < len(text):
                last_period = text.rfind(".", start, end)
                last_newline = text.rfind("\n", start, end)
                break_point = max(last_period, last_newline)
                if break_point > start + self.chunk_size // 2:
                    end = break_point + 1

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(Chunk(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    char_start=start,
                    char_end=end
                ))
                chunk_index += 1

            start = end - self.overlap if end < len(text) else end

        return chunks