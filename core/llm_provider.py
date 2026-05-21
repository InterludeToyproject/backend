import os
import json
import anthropic
from dotenv import load_dotenv
from typing import List
from dataclasses import dataclass

load_dotenv()

@dataclass
class AnalysisResult:
    overall_risk: str
    violations: List[dict]
    suggestions: List[str]
    summary: str
    approved: bool
    confidence: float = 0.0
    verified: bool = False
    retry_count: int = 0
    verification_note: str = ""
    translated_summary: str = ""

class ClaudeProvider:
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self.model = "claude-sonnet-4-5"
        self.max_retries = 1

    def _parse_json(self, raw: str) -> dict:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        return json.loads(raw)

    def generate_corrected_content(self, content: str, violations: list, suggestions: list) -> str:
        """수정본 생성 — 버튼 클릭 시에만 호출"""
        violations_str = "\n".join([
            f"- {v.get('flagged_text', '')}"
            for v in violations if v.get('flagged_text')
        ])
        suggestions_str = "\n".join(suggestions)

        prompt = f"""당신은 금융 준법심의 전문가입니다.
아래 원본 콘텐츠를 준법에 맞게 수정해주세요.

[원본 콘텐츠]
{content}

[위반 항목]
{violations_str}

[수정 제안]
{suggestions_str}

수정된 전체 콘텐츠만 출력하세요. 설명 없이 수정본 텍스트만 출력합니다."""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()

    def _judge(self, content: str, rule_violations: List,
               rag_references: List[dict], language: str = "ko") -> dict:
        """Claude AI 판단"""
        lang_instruction = ""
        if language != "ko":
            lang_instruction = """
[언어 처리 안내]
입력된 콘텐츠는 한국어가 아닙니다.
1. 먼저 한국어로 번역하여 의미를 파악하세요
2. 번역된 내용을 기준으로 한국 금융규제 위반 여부를 판단하세요
3. flagged_text는 원문 표현을 그대로 사용하세요
"""

        rag_context = ""
        for ref in rag_references[:2]:
            rag_context += f"\n---\n{ref['law_name']}\n{ref['content'][:150]}"

        rule_context = ""
        for v in rule_violations:
            rule_context += f"\n- [{v.severity}] {v.rule_name}: {v.flagged_text[:30]}..."

        prompt = f"""당신은 JB금융그룹의 준법심의 AI입니다.
아래 금융 마케팅 콘텐츠를 분석하여 준법 위반 여부를 판단해주세요.
{lang_instruction}

[심의 대상 콘텐츠]
{content}

[1차 Rule Engine 탐지 결과]
{rule_context if rule_context else "탐지된 위반 없음"}

[관련 규제 조문]
{rag_context if rag_context else "참조 조문 없음"}

JSON 형식으로만 응답하세요:
{{
    "detected_language": "{language}",
    "translated_summary": "",
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
    "summary": "심의 결과 요약",
    "approved": false
}}"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        return self._parse_json(response.content[0].text.strip())

    def _verify(self, judgment: dict) -> dict:
        """자가 검증 — 로직 기반 (API 호출 없음, 토큰 0)"""
        overall_risk = judgment.get("overall_risk", "")
        violations = judgment.get("violations", [])
        violations_count = len(violations)

        # 유효한 위험도 체크
        valid_risks = ["HIGH", "MEDIUM", "LOW", "SAFE"]
        if overall_risk not in valid_risks:
            return {
                "verified": False,
                "confidence": 0.3,
                "issues": ["유효하지 않은 위험도"],
                "correction_needed": False,
                "note": "위험도 오류"
            }

        # SAFE인데 위반 있으면 불일치
        if overall_risk == "SAFE" and violations_count > 0:
            return {
                "verified": True,
                "confidence": 0.7,
                "issues": [],
                "correction_needed": False,
                "note": f"위반 {violations_count}건 탐지 — SAFE 재조정"
            }

        # 정상 케이스
        confidence = 0.95 if overall_risk in ["HIGH", "MEDIUM"] and violations_count > 0 else 0.85

        return {
            "verified": True,
            "confidence": confidence,
            "issues": [],
            "correction_needed": False,
            "note": f"위반 {violations_count}건 탐지 — 검증 완료"
        }

    def analyze_content(
        self,
        content: str,
        rule_violations: List,
        rag_references: List[dict],
        language: str = "ko"
    ) -> AnalysisResult:

        retry_count = 0
        final_judgment = None
        final_verification = None

        for attempt in range(self.max_retries + 1):
            try:
                judgment = self._judge(content, rule_violations, rag_references, language)
            except Exception as e:
                print(f"_judge 실패 (시도 {attempt+1}): {e}")
                if attempt == self.max_retries:
                    raise
                continue

            # 로직 기반 검증 (API 호출 없음)
            verification = self._verify(judgment)

            retry_count = attempt
            final_judgment = judgment
            final_verification = verification

            # 검증 통과하면 바로 종료
            if verification.get("verified"):
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
            verification_note=final_verification.get("note", ""),
            translated_summary=final_judgment.get("translated_summary", "")
        )