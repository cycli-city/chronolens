import os
import re
from pathlib import Path
from app.pipelines.document_parser import DocumentParser
from app.pipelines.chunker import TextChunker
from app.core.temporal_vector_store import TemporalVectorStore
from typing import Dict

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}
MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


class SecurityError(Exception):
    pass


class IngestionPipeline:
    def __init__(self):
        self.parser = DocumentParser()
        self.chunker = TextChunker(chunk_size=800, overlap=150)
        self.vector_store = TemporalVectorStore()

    def _validate_file(self, file_path: str) -> None:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if path.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise SecurityError(f"File type '{path.suffix}' not allowed.")
        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise SecurityError(f"File too large ({file_size/1024/1024:.1f}MB). Max: {MAX_FILE_SIZE_MB}MB")
        if file_size == 0:
            raise SecurityError("File is empty.")
        if ".." in file_path:
            raise SecurityError("Path traversal detected.")

    def _sanitize(self, value: str, max_length: int = 200) -> str:
        if not isinstance(value, str):
            value = str(value)
        value = re.sub(r'[\x00-\x1f\x7f]', '', value)
        return value[:max_length].strip()

    def _validate_timestamp(self, timestamp: str) -> str:
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', timestamp):
            raise ValueError(f"Invalid timestamp format: '{timestamp}'. Use YYYY-MM-DD.")
        return timestamp

    def ingest(
        self,
        user_id: str,
        file_path: str,
        document_id: str,
        version: int,
        timestamp: str,
        doc_name: str,
        doc_type: str = "general"
    ) -> Dict:
        self._validate_file(file_path)
        timestamp = self._validate_timestamp(timestamp)
        doc_name = self._sanitize(doc_name)
        doc_type = self._sanitize(doc_type, max_length=50)
        document_id = self._sanitize(document_id, max_length=100)

        if not isinstance(version, int) or version < 1:
            raise ValueError("Version must be a positive integer.")

        raw_text = self.parser.parse(file_path)
        if not raw_text:
            raise ValueError("No text extracted from document")

        chunks = self.chunker.chunk(raw_text)
        chunk_dicts = [{"text": c.text, "chunk_index": c.chunk_index} for c in chunks]

        chunk_ids = self.vector_store.add_document_version(
            user_id=user_id,
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