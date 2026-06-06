import os
import re
import uuid
import tempfile
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, Request

from app.core.auth import verify_api_key
from app.core.security_scanner import SecurityScanner
from app.core.audit_logger import AuditLogger
from app.pipelines.ingestion import IngestionPipeline, SecurityError
from app.core.temporal_vector_store import TemporalVectorStore
from app.models.schemas import IngestResponse, DocumentVersionsResponse, VersionInfo

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}
MAX_UPLOAD_SIZE = 20 * 1024 * 1024

pipeline = IngestionPipeline()
vector_store = TemporalVectorStore()
scanner = SecurityScanner()
auditor = AuditLogger()


def _safe_filename(filename: str) -> str:
    safe = Path(filename).name
    safe = "".join(c for c in safe if c.isalnum() or c in "._-")
    return safe[:100]


@router.post("/upload", response_model=IngestResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    document_id: str = Form(...),
    version: int = Form(...),
    timestamp: str = Form(...),
    doc_name: str = Form(...),
    doc_type: str = Form(default="general"),
    user_id: str = Depends(verify_api_key)
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    safe_name = _safe_filename(file.filename)
    suffix = Path(safe_name).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"File type not allowed.")

    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large.")
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    client_ip = request.client.host if request.client else "unknown"
    try:
        raw_text_preview = contents.decode("utf-8", errors="ignore")
        scan_result = scanner.scan(raw_text_preview)
        auditor.log_upload(
            document_id=document_id, version=version, filename=safe_name,
            ip=f"{client_ip} user={user_id[:8]}",
            scan_passed=scan_result.passed, findings_count=len(scan_result.findings)
        )
        if not scan_result.passed:
            critical = scan_result.critical
            auditor.log_security_block(
                reason="critical_secrets_detected",
                ip=f"{client_ip} user={user_id[:8]}",
                detail=f"doc={document_id} v={version} findings={len(critical)}"
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "Document blocked by security scanner",
                    "reason": "Critical sensitive data detected before ingestion",
                    "findings": [
                        {"type": f.type, "description": f.description,
                         "match": f.match, "line": f.line_hint}
                        for f in critical
                    ]
                }
            )
    except HTTPException:
        raise
    except Exception:
        pass

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=suffix,
            prefix=f"chronolens_{uuid.uuid4().hex[:8]}_"
        ) as tmp:
            tmp.write(contents)
            temp_path = tmp.name

        result = pipeline.ingest(
            user_id=user_id,
            file_path=temp_path,
            document_id=document_id,
            version=version,
            timestamp=timestamp,
            doc_name=doc_name,
            doc_type=doc_type
        )
        return IngestResponse(**result)

    except SecurityError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            try: os.unlink(temp_path)
            except Exception: pass


@router.get("/{document_id}/versions", response_model=DocumentVersionsResponse)
async def get_versions(document_id: str, user_id: str = Depends(verify_api_key)):
    if not re.match(r"^[a-zA-Z0-9_\-]+$", document_id):
        raise HTTPException(status_code=400, detail="Invalid document_id format")

    versions = vector_store.get_all_versions(user_id, document_id)
    if not versions:
        raise HTTPException(status_code=404, detail=f"No versions found for: {document_id}")

    return DocumentVersionsResponse(
        document_id=document_id,
        versions=[VersionInfo(**v) for v in versions],
        total_versions=len(versions)
    )


@router.get("/list")
async def list_documents(user_id: str = Depends(verify_api_key)):
    """Return all documents owned by the current user."""
    return {"documents": vector_store.list_user_documents(user_id)}


@router.get("/stats")
async def get_stats(user_id: str = Depends(verify_api_key)):
    return {
        "total_chunks": vector_store.count(user_id=user_id),
        "status": "operational"
    }


@router.get("/audit-log")
async def get_audit_log(user_id: str = Depends(verify_api_key)):
    return {"entries": auditor.get_recent(50)}