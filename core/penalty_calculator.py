from typing import List

# 법령별 과태료 기준 (실제 금융관련법 기준)
PENALTY_RULES = [
    {
        "violation_types": ["투자위험 미고지", "투자위험 허위 표시", "원금 보장 허위 표현"],
        "law": "금융소비자보호법 제19조 (설명의무 위반)",
        "fine_min": 10000000,
        "fine_max": 50000000,
        "sanction": "기관 경고 또는 업무 일부 정지",
        "cases": [
            {"date": "2024.08", "org": "A저축은행", "fine": 30000000, "action": "기관경고"},
            {"date": "2024.03", "org": "B투자증권", "fine": 50000000, "action": "업무정지 1개월"},
        ]
    },
    {
        "violation_types": ["허위·과장 광고", "비교 광고 근거 미제시", "고수익 과장 표현"],
        "law": "금융소비자보호법 제22조 (광고 규제 위반)",
        "fine_min": 5000000,
        "fine_max": 30000000,
        "sanction": "시정명령 또는 기관 주의",
        "cases": [
            {"date": "2024.11", "org": "C카드사", "fine": 20000000, "action": "시정명령"},
            {"date": "2024.06", "org": "D은행", "fine": 15000000, "action": "기관주의"},
        ]
    },
    {
        "violation_types": ["개인정보 무단 수집 표현", "동의 없는 개인정보"],
        "law": "개인정보보호법 제15조 (수집·이용 위반)",
        "fine_min": 30000000,
        "fine_max": 300000000,
        "sanction": "과징금 부과 및 시정명령",
        "cases": [
            {"date": "2024.09", "org": "E핀테크", "fine": 150000000, "action": "과징금+시정명령"},
            {"date": "2024.01", "org": "F보험사", "fine": 50000000, "action": "과징금"},
        ]
    },
    {
        "violation_types": ["불완전판매 표현", "필수 고지사항 누락", "긴급성·희소성 과장"],
        "law": "금융소비자보호법 제21조 (불공정 영업행위)",
        "fine_min": 5000000,
        "fine_max": 50000000,
        "sanction": "과태료 부과",
        "cases": [
            {"date": "2024.10", "org": "G증권사", "fine": 30000000, "action": "과태료+경고"},
            {"date": "2024.05", "org": "H캐피탈", "fine": 10000000, "action": "과태료"},
        ]
    },
    {
        "violation_types": ["신용정보 무단 수집", "개인신용정보 언급"],
        "law": "신용정보법 제32조 (개인신용정보 제공·활용)",
        "fine_min": 10000000,
        "fine_max": 100000000,
        "sanction": "과태료 및 업무 개선 명령",
        "cases": [
            {"date": "2024.07", "org": "I대부업체", "fine": 50000000, "action": "업무개선명령"},
        ]
    }
]

RISK_LABELS = {
    "HIGH": {"label": "매우 높음", "color": "🔴", "reputation": "심각"},
    "MEDIUM": {"label": "보통", "color": "🟡", "reputation": "주의"},
    "LOW": {"label": "낮음", "color": "🟢", "reputation": "경미"},
    "SAFE": {"label": "없음", "color": "✅", "reputation": "없음"}
}

from core.sanction_crawler import SanctionCrawler

def calculate_penalty(violations: List[dict], overall_risk: str) -> dict:
    if not violations or overall_risk == "SAFE":
        return {
            "total_fine_min": 0,
            "total_fine_max": 0,
            "sanctions": [],
            "cases": [],
            "risk_level": "없음",
            "reputation_risk": "없음",
            "matched_rules": []
        }

    matched_rules = []
    total_min = 0
    total_max = 0
    all_sanctions = []

    violation_types = [v.get("type", "") for v in violations]

    for rule in PENALTY_RULES:
        for vtype in violation_types:
            matched = any(keyword in vtype for keyword in rule["violation_types"])
            if matched:
                if rule not in matched_rules:
                    matched_rules.append(rule)
                    total_min += rule["fine_min"]
                    total_max += rule["fine_max"]
                    all_sanctions.append(rule["sanction"])
                break

    multiplier = {"HIGH": 1.0, "MEDIUM": 0.6, "LOW": 0.3}.get(overall_risk, 0.5)
    estimated_fine = int((total_min + total_max) / 2 * multiplier)
    risk_info = RISK_LABELS.get(overall_risk, RISK_LABELS["MEDIUM"])

    # 실제 금감원 제재 사례 크롤링
    try:
        crawler = SanctionCrawler()
        real_cases = crawler.find_relevant_sanctions(violation_types)
    except:
        real_cases = []

    return {
        "total_fine_min": total_min,
        "total_fine_max": total_max,
        "estimated_fine": estimated_fine,
        "sanctions": list(set(all_sanctions)),
        "cases": real_cases,
        "risk_level": risk_info["label"],
        "risk_color": risk_info["color"],
        "reputation_risk": risk_info["reputation"],
        "matched_rules": [
            {
                "law": r["law"],
                "fine_range": f"{r['fine_min']//10000}만원 ~ {r['fine_max']//10000}만원"
            }
            for r in matched_rules
        ]
    }
