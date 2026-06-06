from fastapi import APIRouter, Depends, HTTPException
from app.core.causal_graph import CausalGraphEngine
from app.core.semantic_diff import SemanticDiffEngine
from pydantic import BaseModel, Field
from typing import Optional
from app.core.auth import verify_api_key
from app.core.temporal_rag import TemporalRAGEngine
from fastapi import APIRouter, Depends, HTTPException, Request
from app.core.security_scanner import detect_prompt_injection
from app.core.audit_logger import AuditLogger



router = APIRouter(prefix="/api/query", tags=["query"])

rag_engine = TemporalRAGEngine()
diff_engine = SemanticDiffEngine()
auditor = AuditLogger()
graph_engine = CausalGraphEngine()


class QueryRequest(BaseModel):
    document_id: str = Field(..., min_length=1, max_length=100)
    question: str = Field(..., min_length=3, max_length=1000)


class CompareRequest(BaseModel):
    document_id: str = Field(..., min_length=1, max_length=100)
    version_a: int = Field(..., ge=1)
    version_b: int = Field(..., ge=1)
    aspect: Optional[str] = Field(None, max_length=200)


@router.post("/ask")
async def ask_question(
    request: QueryRequest,
    api_key: str = Depends(verify_api_key)
):
    """Ask any question about a document."""
    injection = detect_prompt_injection(request.question)
    if injection["injection_detected"]:
        auditor.log_security_block(
            reason="prompt_injection",
            ip="api",
            detail=request.question[:100]
        )
        raise HTTPException(
            status_code=400,
            detail="Query blocked: potential prompt injection detected."
        )
    try:
        result = rag_engine.query(
            question=request.question,
            document_id=request.document_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_versions(
    request: CompareRequest,
    api_key: str = Depends(verify_api_key)
):
    """Compare two versions of a document — the temporal magic."""
    if request.version_a == request.version_b:
        raise HTTPException(
            status_code=400,
            detail="version_a and version_b must be different"
        )
    try:
        result = rag_engine.compare_versions(
            document_id=request.document_id,
            version_a=request.version_a,
            version_b=request.version_b,
            aspect=request.aspect
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline/{document_id}")
async def get_timeline(
    document_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get the full evolution timeline of a document."""
    try:
        result = rag_engine.timeline_summary(document_id=document_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/semantic-diff")
async def semantic_diff(
    request: CompareRequest,
    api_key: str = Depends(verify_api_key)
):
    """Embedding-level semantic diff between two versions."""
    if request.version_a == request.version_b:
        raise HTTPException(
            status_code=400,
            detail="version_a and version_b must be different"
        )
    try:
        result = diff_engine.diff(
            request.document_id, request.version_a, request.version_b
        )
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/causal-graph/{document_id}")
async def causal_graph(
    document_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Build the causal timeline graph for a document."""
    import re
    if not re.match(r"^[a-zA-Z0-9_\-]+$", document_id):
        raise HTTPException(status_code=400, detail="Invalid document_id format")
    try:
        result = graph_engine.build(document_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))