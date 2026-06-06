import fitz  # PyMuPDF
from docx import Document
from pathlib import Path
from typing import Optional


class DocumentParser:
    """Extracts raw text from PDF and DOCX files."""

    @staticmethod
    def parse_pdf(file_path: str) -> str:
        """Extract text from PDF file."""
        text = ""
        try:
            doc = fitz.open(file_path)
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                text += f"\n[PAGE {page_num + 1}]\n{page_text}"
            doc.close()
            return text.strip()
        except Exception as e:
            raise Exception(f"Failed to parse PDF: {str(e)}")

    @staticmethod
    def parse_docx(file_path: str) -> str:
        """Extract text from DOCX file."""
        try:
            doc = Document(file_path)
            text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
            return text.strip()
        except Exception as e:
            raise Exception(f"Failed to parse DOCX: {str(e)}")

    @classmethod
    def parse(cls, file_path: str) -> str:
        """Auto-detect file type and parse."""
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            return cls.parse_pdf(file_path)
        elif suffix in [".docx", ".doc"]:
            return cls.parse_docx(file_path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")