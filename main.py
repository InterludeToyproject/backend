import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import json
import traceback
from datetime import datetime
from core.hallucination_detector import verify_violations, get_hallucination_summary

from core.rule_engine import RuleEngine
from core.llm_provider import ClaudeProvider
from core.anonymizer import Anonymizer
from core.rag import search_regulations
from core.highlighter import highlight_content
from core.language_detector import detect_language, LANGUAGE_NAMES, LANGUAGE_FLAGS
from core.penalty_calculator import calculate_penalty
from core.report_generator import ReportGenerator
from core.crawler import RegulationCrawler
from core.rule_extractor import RuleExtractor
from core.injection_detector import InjectionDetector
from db.database import Database

app = FastAPI(title="RegRadar API", version="1.0.0")

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print("=== 에러 발생 ===")
    traceback.print_exc()
    print("=================")
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )

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
injection_detector = InjectionDetector()
report_generator = ReportGenerator()
crawler = RegulationCrawler()
rule_extractor = RuleExtractor()

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

        #0단계: 프롬프트 인젝션 탐지
        injection_result = injection_detector.detect(content)
        if injection_result.blocked:
            return {
                "review_id": None,
                "overall_risk": "BLOCKED",
                "approved": False,
                "blocked": True,
                "threat_level": injection_result.threat_level,
                "block_reason": injection_result.reason,
                "security_alert": True,
                "highlighted_content": "",
                "rule_violations": [],
                "ai_violations": [],
                "suggestions": ["보안 위협이 탐지되어 심의가 차단되었습니다."],
                "summary": injection_result.reason,
                "pii_detected": [],
                "rag_references": [],
                "penalty": {},
                "confidence": 0,
                "verified": False,
                "retry_count": 0,
                "verification_note": "",
                "detected_language": "ko",
                "language_name": "한국어",
                "language_flag": "🇰🇷",
                "translated_summary": ""
            }

        # 1단계: 익명화
        anon_result = anonymizer.anonymize(content)
        safe_content = anon_result.anonymized_text
        
        # 1.5단계: 언어 감지  ← 추가
        detected_lang = detect_language(content)

        # 2단계: Rule Engine 1차 필터
        rule_violations = rule_engine.analyze(content)

        # 3단계: RAG 검색
        search_query = content[:100]
        rag_results = search_regulations(search_query, k=3)

        # 4단계: Claude 최종 판단 (익명화된 텍스트로)
        analysis = claude.analyze_content(
            safe_content,
            rule_violations,
            rag_results,
            language=detected_lang
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

        # 6단계: 하이라이팅 생성  ← 이 줄 추가
        highlighted_html = highlight_content(
            content,
            analysis.violations,
            rule_violations
        )
        
        # 환각 탐지 — 조문 검증
        verified_violations = verify_violations(analysis.violations)
        hallucination_summary = get_hallucination_summary(verified_violations)
        
        # 과태료 계산
        penalty = calculate_penalty(analysis.violations, analysis.overall_risk)

        return {
            "review_id": review_id,
            "content": content,
            "detected_language": detected_lang,                   
            "language_name": LANGUAGE_NAMES.get(detected_lang, "기타"),  #
            "language_flag": LANGUAGE_FLAGS.get(detected_lang, "🌐"), 
            "overall_risk": analysis.overall_risk,
            "approved": analysis.approved,
            "confidence": analysis.confidence,        
            "verified": analysis.verified,            
            "retry_count": analysis.retry_count,  
            "penalty": penalty,
            "highlighted_content": highlighted_html,
            "ai_violations": verified_violations,      
            "hallucination_summary": hallucination_summary,
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
        import traceback
        error_msg = traceback.format_exc()
        print("######### 에러 #########")
        print(error_msg)
        print("########################")
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/approve")
async def approve_content(request: ApprovalRequest):
    """심의 결과 승인/반려 + 레포트 자동 생성"""
    try:
        db.update_approval(
            review_id=request.review_id,
            action=request.action,
            reviewer=request.reviewer,
            comment=request.comment
        )

        # 전체 심의 데이터 조회
        full_review = db.get_review(request.review_id)

        review_data = {
            "review_id": request.review_id,
            "content_type": full_review.get("content_type", ""),
            "author": full_review.get("author", ""),
            "reviewer": request.reviewer,
            "comment": request.comment,
            "overall_risk": full_review.get("overall_risk", ""),
            "confidence": full_review.get("confidence", 0),
            "content": full_review.get("content", ""),
            "summary": full_review.get("summary", ""),
            "violations": full_review.get("violations", []),
            "suggestions": full_review.get("suggestions", []),
        }

        # 레포트 생성
        if request.action == "approve":
            report = report_generator.generate_approval_report(review_data)
        else:
            report = report_generator.generate_rejection_report(review_data)

        return {
            "review_id": request.review_id,
            "action": request.action,
            "reviewer": request.reviewer,
            "timestamp": datetime.now().isoformat(),
            "report": report
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
    
@app.get("/crawl-regulations")
async def crawl_regulations():
    """규제 공시 실시간 크롤링"""
    try:
        items = crawler.crawl_all()
        analyzed = crawler.analyze_relevance(items)
        
        high_count = sum(1 for i in analyzed if i.get("relevance") == "HIGH")
        medium_count = sum(1 for i in analyzed if i.get("relevance") == "MEDIUM")

        return {
            "total": len(analyzed),
            "high_relevance": high_count,
            "medium_relevance": medium_count,
            "crawled_at": datetime.now().isoformat(),
            "items": analyzed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/extract-rules")
async def extract_rules():
    """규제문서에서 규칙 자동 추출"""
    try:
        queries = [
            "금융상품 광고 금지 표현",
            "개인정보 수집 동의",
            "투자 위험 고지 의무",
            "불완전판매 금지",
            "금융소비자 보호 의무"
        ]

        total_added = rule_extractor.extract_from_vectorstore(queries)
        stats = rule_extractor.get_stats()

        # Rule Engine 재로드
        rule_engine.rules = rule_engine._load_rules()
        rule_engine._load_dynamic_rules()

        return {
            "newly_added": total_added,
            "total_rules": stats["total"] + 20,
            "dynamic_rules": stats,
            "message": f"규제문서 분석 완료. {total_added}개 규칙 자동 추출"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/rules/stats")
async def get_rules_stats():
    """현재 적용 중인 규칙 통계"""
    dynamic_stats = rule_extractor.get_stats()
    return {
        "static_rules": 20,
        "dynamic_rules": dynamic_stats["total"],
        "total_rules": 20 + dynamic_stats["total"],
        "by_severity": {
            "HIGH": dynamic_stats["high"],
            "MEDIUM": dynamic_stats["medium"],
            "LOW": dynamic_stats["low"]
        }
    }
    
@app.get("/security/logs")
async def get_security_logs():
    """보안 이벤트 로그 조회"""
    logs = injection_detector.get_security_logs()
    stats = injection_detector.get_stats()
    return {"logs": logs, "stats": stats}

class CorrectionRequest(BaseModel):
    review_id: int
    content: str

@app.post("/generate-correction")
async def generate_correction(request: CorrectionRequest):
    """수정본 생성 (버튼 클릭 시에만 호출)"""
    try:
        review = db.get_review(request.review_id)
        if not review:
            raise HTTPException(status_code=404, detail="심의 결과를 찾을 수 없습니다")

        violations = review.get("violations", [])
        suggestions = review.get("suggestions", [])

        corrected = claude.generate_corrected_content(
            request.content,
            violations,
            suggestions
        )

        return {
            "review_id": request.review_id,
            "corrected_content": corrected
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
