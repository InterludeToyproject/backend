import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import json
from datetime import datetime

from core.rule_engine import RuleEngine
from core.llm_provider import ClaudeProvider
from core.anonymizer import Anonymizer
from core.rag import search_regulations
from db.database import Database

app = FastAPI(title="RegRadar API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 모듈 초기화
rule_engine = RuleEngine()
claude = ClaudeProvider()
anonymizer = Anonymizer()
db = Database()

# ==========================================
# 요청/응답 모델
# ==========================================

class ContentRequest(BaseModel):
    content: str
    content_type: Optional[str] = "마케팅문자"
    author: Optional[str] = "작성자"

class ApprovalRequest(BaseModel):
    review_id: int
    action: str  # approve / reject
    reviewer: str
    comment: Optional[str] = ""

class RegulationUploadRequest(BaseModel):
    regulation_text: str
    regulation_name: str

# ==========================================
# 엔드포인트
# ==========================================

@app.get("/")
def root():
    return {"service": "RegRadar", "status": "정상 동작"}

@app.post("/scan-content")
async def scan_content(request: ContentRequest):
    """콘텐츠 준법 심의"""
    try:
        content = request.content

        # 1단계: 익명화
        anon_result = anonymizer.anonymize(content)
        safe_content = anon_result.anonymized_text

        # 2단계: Rule Engine 1차 필터
        rule_violations = rule_engine.analyze(content)

        # 3단계: RAG 검색
        search_query = content[:100]
        rag_results = search_regulations(search_query, k=3)

        # 4단계: Claude 최종 판단 (익명화된 텍스트로)
        analysis = claude.analyze_content(
            safe_content,
            rule_violations,
            rag_results
        )

        # 5단계: DB 저장
        review_id = db.save_review(
            content=content,
            content_type=request.content_type,
            author=request.author,
            overall_risk=analysis.overall_risk,
            violations=analysis.violations,
            suggestions=analysis.suggestions,
            summary=analysis.summary,
            pii_detected=anon_result.detected_pii
        )

        return {
            "review_id": review_id,
            "overall_risk": analysis.overall_risk,
            "approved": analysis.approved,
            "rule_violations": [
                {
                    "rule_id": v.rule_id,
                    "rule_name": v.rule_name,
                    "severity": v.severity,
                    "flagged_text": v.flagged_text,
                    "law_reference": v.law_reference
                }
                for v in rule_violations
            ],
            "ai_violations": analysis.violations,
            "suggestions": analysis.suggestions,
            "summary": analysis.summary,
            "pii_detected": anon_result.detected_pii,
            "rag_references": [
                {
                    "law_name": r["law_name"],
                    "content": r["content"][:200]
                }
                for r in rag_results
            ]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/approve")
async def approve_content(request: ApprovalRequest):
    """심의 결과 승인/반려"""
    try:
        db.update_approval(
            review_id=request.review_id,
            action=request.action,
            reviewer=request.reviewer,
            comment=request.comment
        )
        return {
            "review_id": request.review_id,
            "action": request.action,
            "reviewer": request.reviewer,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/reviews")
async def get_reviews(limit: int = 20):
    """심의 이력 조회"""
    reviews = db.get_reviews(limit=limit)
    return {"reviews": reviews}


@app.get("/reviews/{review_id}")
async def get_review(review_id: int):
    """특정 심의 결과 조회"""
    review = db.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="심의 결과를 찾을 수 없습니다")
    return review


@app.get("/stats")
async def get_stats():
    """대시보드 통계"""
    return db.get_stats()

@app.post("/upload-regulation")
async def upload_regulation(request: RegulationUploadRequest):
    """규제 변경 업로드 + 기존 콘텐츠 영향 분석"""
    try:
        # 기존 승인 콘텐츠 조회
        reviews = db.get_reviews(limit=100)
        approved_reviews = [r for r in reviews if r["approved"] == "APPROVED"]

        affected = []
        high_count = 0
        medium_count = 0

        for review in approved_reviews:
            full_review = db.get_review(review["id"])
            if not full_review:
                continue

            # 변경된 규제 기준으로 재검토
            rag_results = search_regulations(request.regulation_text[:100], k=3)
            rule_violations = rule_engine.analyze(full_review["content"])
            analysis = claude.analyze_content(
                full_review["content"],
                rule_violations,
                rag_results
            )

            if analysis.overall_risk in ["HIGH", "MEDIUM"]:
                affected.append({
                    "id": review["id"],
                    "content": full_review["content"],
                    "content_type": review["content_type"],
                    "risk": analysis.overall_risk,
                    "reason": analysis.summary,
                    "recommendation": analysis.suggestions[0] if analysis.suggestions else ""
                })
                if analysis.overall_risk == "HIGH":
                    high_count += 1
                else:
                    medium_count += 1

        # 변경 규제 RAG에 추가
        from langchain.schema import Document
        from core.rag import load_vectorstore
        vectorstore = load_vectorstore()
        doc = Document(
            page_content=request.regulation_text,
            metadata={"source_file": request.regulation_name, "law_name": request.regulation_name}
        )
        vectorstore.add_documents([doc])

        summary = f"{request.regulation_name} 변경으로 인해 기존 승인 콘텐츠 {len(affected)}건이 영향을 받습니다."
        if high_count > 0:
            summary += f" {high_count}건은 즉시 수정이 필요합니다."

        return {
            "affected_count": len(affected),
            "high_risk_count": high_count,
            "medium_risk_count": medium_count,
            "affected_reviews": affected,
            "summary": summary
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/retroactive-scan")
async def retroactive_scan(request: dict):
    """소급 위반 탐지"""
    try:
        query = request.get("query", "")
        reviews = db.get_reviews(limit=100)
        approved_reviews = [r for r in reviews if r["approved"] == "APPROVED"]

        flagged = []
        high_count = 0
        medium_count = 0

        for review in approved_reviews:
            full_review = db.get_review(review["id"])
            if not full_review:
                continue

            rag_results = search_regulations(query, k=3)
            rule_violations = rule_engine.analyze(full_review["content"])
            analysis = claude.analyze_content(
                full_review["content"],
                rule_violations,
                rag_results
            )

            if analysis.overall_risk in ["HIGH", "MEDIUM"]:
                flagged.append({
                    "id": review["id"],
                    "content": full_review["content"],
                    "content_type": review["content_type"],
                    "risk": analysis.overall_risk,
                    "reason": analysis.summary,
                    "recommendation": analysis.suggestions[0] if analysis.suggestions else ""
                })
                if analysis.overall_risk == "HIGH":
                    high_count += 1
                else:
                    medium_count += 1

        return {
            "total_scanned": len(approved_reviews),
            "high_count": high_count,
            "medium_count": medium_count,
            "flagged_reviews": flagged
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
