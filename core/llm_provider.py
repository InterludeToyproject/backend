import os
import json
import anthropic
from dotenv import load_dotenv
from typing import List
from dataclasses import dataclass, field

load_dotenv()

@dataclass
class AnalysisResult:
    overall_risk: str
    violations: List[dict]
    suggestions: List[str]
    summary: str
    approved: bool
    confidence: float = 0.0        # 신뢰도 점수
    verified: bool = False         # 검증 통과 여부
    retry_count: int = 0           # 재시도 횟수
    verification_note: str = ""    # 검증 메모

class ClaudeProvider:
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self.model = "claude-sonnet-4-5"
        self.max_retries = 2       # 최대 재시도 횟수

    def _parse_json(self, raw: str) -> dict:
        """JSON 파싱 헬퍼"""
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        return json.loads(raw)

    def _judge(self, content: str, rule_violations: List, rag_references: List[dict]) -> dict:
        """1차 판단"""
        rag_context = ""
        for ref in rag_references[:3]:
            rag_context += f"\n---\n{ref['law_name']}\n{ref['content'][:300]}"

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

다음 JSON 형식으로만 응답하세요:
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
    "suggestions": ["수정 제안 1", "수정 제안 2"],
    "summary": "전체 심의 결과 요약 (2-3문장)",
    "approved": false
}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        return self._parse_json(response.content[0].text.strip())

    def _verify(self, content: str, judgment: dict, rag_references: List[dict]) -> dict:
        """2차 자가 검증"""
        rag_context = ""
        for ref in rag_references[:3]:
            rag_context += f"\n---\n{ref['law_name']}\n{ref['content'][:300]}"

        violations_str = json.dumps(judgment.get("violations", []), ensure_ascii=False)

        prompt = f"""당신은 준법심의 검증 AI입니다.
아래 1차 판단 결과가 규제 조문과 일치하는지 검증하세요.

[원본 콘텐츠]
{content}

[1차 판단 결과]
위험도: {judgment.get('overall_risk')}
위반항목: {violations_str}

[참조 규제 조문]
{rag_context if rag_context else "참조 조문 없음"}

다음 JSON 형식으로만 응답하세요:
{{
    "verified": true 또는 false,
    "confidence": 0.0~1.0 사이 숫자 (판단 신뢰도),
    "issues": ["검증 실패 이유 (있을 경우)"],
    "correction_needed": true 또는 false,
    "corrected_risk": "수정된 위험도 (correction_needed가 true일 때만)",
    "note": "검증 결과 한줄 요약"
}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )
        return self._parse_json(response.content[0].text.strip())

    def analyze_content(
        self,
        content: str,
        rule_violations: List,
        rag_references: List[dict]
    ) -> AnalysisResult:

        retry_count = 0
        final_judgment = None
        final_verification = None

        for attempt in range(self.max_retries + 1):
            # 1차 판단
            judgment = self._judge(content, rule_violations, rag_references)

            # 2차 검증
            verification = self._verify(content, judgment, rag_references)

            confidence = verification.get("confidence", 0.5)
            verified = verification.get("verified", False)
            correction_needed = verification.get("correction_needed", False)

            # 검증 통과 or 마지막 시도
            if verified and not correction_needed:
                final_judgment = judgment
                final_verification = verification
                break

            # 수정 필요한 경우 위험도 교정
            if correction_needed:
                corrected_risk = verification.get("corrected_risk")
                if corrected_risk:
                    judgment["overall_risk"] = corrected_risk

            retry_count = attempt
            final_judgment = judgment
            final_verification = verification

            # 신뢰도 높으면 재시도 불필요
            if confidence >= 0.85:
                break

        return AnalysisResult(
            overall_risk=final_judgment.get("overall_risk", "MEDIUM"),
            violations=final_judgment.get("violations", []),
            suggestions=final_judgment.get("suggestions", []),
            summary=final_judgment.get("summary", ""),
            approved=final_judgment.get("approved", False),
            confidence=final_verification.get("confidence", 0.0),
            verified=final_verification.get("verified", False),
            retry_count=retry_count,
            verification_note=final_verification.get("note", "")
        )