import os
import anthropic
from dotenv import load_dotenv
from typing import List
from dataclasses import dataclass

load_dotenv()

@dataclass
class AnalysisResult:
    overall_risk: str          # HIGH / MEDIUM / LOW / SAFE
    violations: List[dict]     # 위반 항목 목록
    suggestions: List[str]     # 수정 제안
    summary: str               # 전체 요약
    approved: bool             # 승인 가능 여부

class ClaudeProvider:
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self.model = "claude-sonnet-4-5"

    def analyze_content(
        self,
        content: str,
        rule_violations: List,
        rag_references: List[dict]
    ) -> AnalysisResult:

        # RAG 참조 조문 정리
        rag_context = ""
        for ref in rag_references[:3]:
            rag_context += f"\n---\n{ref['law_name']}\n{ref['content'][:300]}"

        # Rule Engine 결과 정리
        rule_context = ""
        for v in rule_violations:
            rule_context += f"\n- [{v.severity}] {v.rule_name}: {v.flagged_text[:50]}..."

        prompt = f"""당신은 JB금융그룹의 준법심의 AI입니다.
아래 금융 마케팅 콘텐츠를 분석하여 준법 위반 여부를 판단해주세요.

[심의 대상 콘텐츠]
{content}

[1차 Rule Engine 탐지 결과]
{rule_context if rule_context else "탐지된 위반 없음"}

[관련 규제 조문]
{rag_context if rag_context else "참조 조문 없음"}

다음 JSON 형식으로만 응답하세요. 다른 텍스트는 절대 포함하지 마세요:
{{
    "overall_risk": "HIGH 또는 MEDIUM 또는 LOW 또는 SAFE",
    "violations": [
        {{
            "type": "위반 유형",
            "flagged_text": "문제 문구",
            "law_reference": "근거 조문",
            "severity": "HIGH 또는 MEDIUM 또는 LOW"
        }}
    ],
    "suggestions": [
        "수정 제안 1",
        "수정 제안 2"
    ],
    "summary": "전체 심의 결과 요약 (2-3문장)",
    "approved": false
}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )

        import json
        raw = response.content[0].text.strip()

        # JSON 파싱
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        result = json.loads(raw)

        return AnalysisResult(
            overall_risk=result.get("overall_risk", "MEDIUM"),
            violations=result.get("violations", []),
            suggestions=result.get("suggestions", []),
            summary=result.get("summary", ""),
            approved=result.get("approved", False)
        )


if __name__ == "__main__":
    import sys
    sys.path.append("backend")
    from core.rule_engine import RuleEngine
    from core.rag import search_regulations

    test_content = """
    이 상품은 원금 보장되는 고수익 투자 상품입니다.
    업계 최고의 수익률을 자랑하며, 손실 위험이 전혀 없습니다.
    지금만 가입 가능한 한정 특가 상품이니 지금 바로 신청하세요.
    """

    print("=== Claude 판단 엔진 테스트 ===")

    # 1차 Rule Engine
    engine = RuleEngine()
    rule_violations = engine.analyze(test_content)
    print(f"Rule Engine: {len(rule_violations)}건 탐지")

    # 2차 RAG 검색
    rag_results = search_regulations("원금보장 금융상품 광고 금지", k=3)
    print(f"RAG 검색: {len(rag_results)}건 참조")

    # 3차 Claude 최종 판단
    claude = ClaudeProvider()
    result = claude.analyze_content(test_content, rule_violations, rag_results)

    print(f"\n🎯 최종 위험도: {result.overall_risk}")
    print(f"✅ 승인 가능: {result.approved}")
    print(f"\n📋 위반 항목:")
    for v in result.violations:
        print(f"  [{v['severity']}] {v['type']}")
        print(f"  근거: {v['law_reference']}")
    print(f"\n💡 수정 제안:")
    for s in result.suggestions:
        print(f"  - {s}")
    print(f"\n📝 요약: {result.summary}")
