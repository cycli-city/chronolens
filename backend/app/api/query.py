import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.core.auth import verify_api_key
from app.core.temporal_rag import TemporalRAGEngine
from app.core.semantic_diff import SemanticDiffEngine
from app.core.causal_graph import CausalGraphEngine
from app.core.security_scanner import detect_prompt_injection
from app.core.audit_logger import AuditLogger

router = APIRouter(prefix="/api/query", tags=["query"])

rag_engine = TemporalRAGEngine()
diff_engine = SemanticDiffEngine()
graph_engine = CausalGraphEngine()
auditor = AuditLogger()


class QueryRequest(BaseModel):
    document_id: str = Field(..., min_length=1, max_length=100)
    question: str = Field(..., min_length=3, max_length=1000)


class CompareRequest(BaseModel):
    document_id: str = Field(..., min_length=1, max_length=100)
    version_a: int = Field(..., ge=1)
    version_b: int = Field(..., ge=1)
    aspect: Optional[str] = Field(None, max_length=200)


@router.post("/ask")
async def ask_question(request: QueryRequest, user_id: str = Depends(verify_api_key)):
    injection = detect_prompt_injection(request.question)
    if injection["injection_detected"]:
        auditor.log_security_block(
            reason="prompt_injection",
            ip=f"user={user_id[:8]}",
            detail=request.question[:100]
        )
        raise HTTPException(status_code=400, detail="Query blocked: potential prompt injection detected.")
    try:
        return rag_engine.query(user_id, request.question, request.document_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_versions(request: CompareRequest, user_id: str = Depends(verify_api_key)):
    if request.version_a == request.version_b:
        raise HTTPException(status_code=400, detail="version_a and version_b must be different")
    try:
        return rag_engine.compare_versions(
            user_id, request.document_id,
            request.version_a, request.version_b, request.aspect
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timeline/{document_id}")
async def get_timeline(document_id: str, user_id: str = Depends(verify_api_key)):
    try:
        return rag_engine.timeline_summary(user_id, document_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/semantic-diff")
async def semantic_diff(request: CompareRequest, user_id: str = Depends(verify_api_key)):
    if request.version_a == request.version_b:
        raise HTTPException(status_code=400, detail="version_a and version_b must be different")
    try:
        result = diff_engine.diff(user_id, request.document_id, request.version_a, request.version_b)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/causal-graph/{document_id}")
async def causal_graph(document_id: str, user_id: str = Depends(verify_api_key)):
    if not re.match(r"^[a-zA-Z0-9_\-]+$", document_id):
        raise HTTPException(status_code=400, detail="Invalid document_id format")
    try:
        result = graph_engine.build(user_id, document_id)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))