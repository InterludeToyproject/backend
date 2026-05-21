import re
from typing import List
from core.rag import search_regulations

def extract_law_reference(law_reference: str) -> dict:
    """
    law_reference에서 법령명과 조문 번호 추출
    예: "금융소비자보호법 제21조" → {"law": "금융소비자보호법", "article": "제21조"}
    """
    patterns = [
        r"([\w\s]+법[\w\s]*)\s*(제\d+조[\w\s]*)",
        r"([\w\s]+법[\w\s]*)\s*(제\d+조)",
        r"([\w\s]+규정[\w\s]*)\s*(제\d+조[\w\s]*)",
    ]
    for pattern in patterns:
        match = re.search(pattern, law_reference)
        if match:
            return {
                "law": match.group(1).strip(),
                "article": match.group(2).strip(),
                "full": law_reference
            }
    return {"law": "", "article": "", "full": law_reference}


def verify_law_reference(law_reference: str, threshold: float = 0.6) -> dict:
    """
    RAG에서 실제 조문 존재 여부 검증
    """
    if not law_reference or len(law_reference) < 5:
        return {
            "verified": False,
            "confidence": 0.0,
            "note": "조문 정보 없음",
            "found_content": ""
        }

    parsed = extract_law_reference(law_reference)

    # RAG 검색 쿼리 구성
    query = law_reference
    if parsed["article"]:
        query = f"{parsed['law']} {parsed['article']}"

    try:
        results = search_regulations(query, k=3)
    except:
        return {
            "verified": False,
            "confidence": 0.0,
            "note": "검색 실패",
            "found_content": ""
        }

    if not results:
        return {
            "verified": False,
            "confidence": 0.0,
            "note": "관련 조문 없음",
            "found_content": ""
        }

    # 최상위 결과 유사도 확인
    best_result = results[0]
    best_score = best_result.get("score", 1.0)

    # ChromaDB L2 거리 기반 점수 (200대가 정상)
    if best_score < 210:
        confidence = 0.95
        verified = True
        note = "✅ 검증됨"
    elif best_score < 250:
        confidence = 0.75
        verified = True
        note = "✅ 검증됨 (유사 조문)"
    elif best_score < 300:
        confidence = 0.5
        verified = False
        note = "⚠️ 조문 불확실"
    else:
        confidence = 0.2
        verified = False
        note = "❌ 조문 미확인"

    return {
        "verified": verified,
        "confidence": confidence,
        "note": note,
        "found_content": best_result.get("content", "")[:100]
    }


def verify_violations(violations: List[dict]) -> List[dict]:
    """
    위반 항목 전체 조문 검증
    """
    verified_violations = []

    for v in violations:
        law_ref = v.get("law_reference", "")
        verification = verify_law_reference(law_ref)

        verified_v = dict(v)
        verified_v["law_verified"] = verification["verified"]
        verified_v["law_confidence"] = verification["confidence"]
        verified_v["law_note"] = verification["note"]
        verified_v["law_found_content"] = verification["found_content"]
        verified_violations.append(verified_v)

    return verified_violations


def get_hallucination_summary(violations: List[dict]) -> dict:
    """
    전체 환각 탐지 요약
    """
    if not violations:
        return {
            "total": 0,
            "verified": 0,
            "unverified": 0,
            "hallucination_risk": "LOW",
            "note": "위반 항목 없음"
        }

    verified_count = sum(1 for v in violations if v.get("law_verified", False))
    unverified_count = len(violations) - verified_count
    verified_ratio = verified_count / len(violations)

    if verified_ratio >= 0.8:
        risk = "LOW"
        note = "조문 근거 신뢰도 높음"
    elif verified_ratio >= 0.5:
        risk = "MEDIUM"
        note = "일부 조문 확인 필요"
    else:
        risk = "HIGH"
        note = "조문 근거 재확인 필요"

    return {
        "total": len(violations),
        "verified": verified_count,
        "unverified": unverified_count,
        "hallucination_risk": risk,
        "note": note
    }
