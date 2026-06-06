import os
import re
from pathlib import Path
from app.pipelines.document_parser import DocumentParser
from app.pipelines.chunker import TextChunker
from app.core.temporal_vector_store import TemporalVectorStore
from typing import Dict

# Security constants
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}
MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


class SecurityError(Exception):
    pass


class IngestionPipeline:
    """
    Full ingestion pipeline:
    File → Validate → Parse → Chunk → Embed → Store with temporal metadata
    """

    def __init__(self):
        self.parser = DocumentParser()
        self.chunker = TextChunker(chunk_size=800, overlap=150)
        self.vector_store = TemporalVectorStore()

    def _validate_file(self, file_path: str) -> None:
        """Security: validate file before processing."""
        path = Path(file_path)

        # Check file exists
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check extension (prevent malicious file types)
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise SecurityError(
                f"File type '{path.suffix}' not allowed. "
                f"Allowed: {ALLOWED_EXTENSIONS}"
            )

        # Check file size (prevent DoS)
        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise SecurityError(
                f"File too large ({file_size / 1024 / 1024:.1f}MB). "
                f"Max allowed: {MAX_FILE_SIZE_MB}MB"
            )

        if file_size == 0:
            raise SecurityError("File is empty.")

        # Prevent path traversal attacks
        resolved = str(path.resolve())
        if ".." in file_path:
            raise SecurityError("Path traversal detected.")

    def _sanitize_metadata(self, value: str, max_length: int = 200) -> str:
        """Sanitize metadata strings."""
        if not isinstance(value, str):
            value = str(value)
        # Remove control characters
        value = re.sub(r'[\x00-\x1f\x7f]', '', value)
        # Truncate to max length
        return value[:max_length].strip()

    def _validate_timestamp(self, timestamp: str) -> str:
        """Validate timestamp is a real date string."""
        import re
        pattern = r'^\d{4}-\d{2}-\d{2}$'
        if not re.match(pattern, timestamp):
            raise ValueError(
                f"Invalid timestamp format: '{timestamp}'. "
                f"Use YYYY-MM-DD format."
            )
        return timestamp

    def ingest(
        self,
        file_path: str,
        document_id: str,
        version: int,
        timestamp: str,
        doc_name: str,
        doc_type: str = "general"
    ) -> Dict:
        """
        Run the full secure ingestion pipeline on a file.
        """
        # Security validations first
        self._validate_file(file_path)
        timestamp = self._validate_timestamp(timestamp)
        doc_name = self._sanitize_metadata(doc_name)
        doc_type = self._sanitize_metadata(doc_type, max_length=50)
        document_id = self._sanitize_metadata(document_id, max_length=100)

        if not isinstance(version, int) or version < 1:
            raise ValueError("Version must be a positive integer.")

        # Step 1: Parse
        raw_text = self.parser.parse(file_path)
        if not raw_text:
            raise ValueError("No text extracted from document")

        # Step 2: Chunk
        chunks = self.chunker.chunk(raw_text)
        chunk_dicts = [
            {"text": c.text, "chunk_index": c.chunk_index}
            for c in chunks
        ]

        # Step 3: Embed + Store
        chunk_ids = self.vector_store.add_document_version(
            document_id=document_id,
            version=version,
            timestamp=timestamp,
            chunks=chunk_dicts,
            doc_name=doc_name,
            doc_type=doc_type
        )

        return {
            "status": "success",
            "document_id": document_id,
            "version": version,
            "chunks_created": len(chunk_ids),
            "total_text_length": len(raw_text)
        }