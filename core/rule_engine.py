import re
from dataclasses import dataclass
from typing import List

@dataclass
class RuleViolation:
    rule_id: str
    rule_name: str
    severity: str  # HIGH / MEDIUM / LOW
    flagged_text: str
    description: str
    law_reference: str

class RuleEngine:
    def __init__(self):
        self.rules = self._load_rules()

    def _load_rules(self):
        return [

            # ==========================================
            # HIGH - 즉시 수정 필요
            # ==========================================
            {
                "id": "R001",
                "name": "원금 보장 허위 표현",
                "severity": "HIGH",
                "patterns": [
                    r"원금\s*보장",
                    r"손실\s*없음",
                    r"절대\s*안전",
                    r"100%\s*수익",
                    r"무조건\s*수익",
                ],
                "description": "원금 보장이 불가능한 금융상품에 보장 표현 사용",
                "law_reference": "금융소비자보호법 제21조 (허위·과장 광고 금지)"
            },
            {
                "id": "R002",
                "name": "고수익 과장 표현",
                "severity": "HIGH",
                "patterns": [
                    r"고수익\s*보장",
                    r"확실한\s*수익",
                    r"반드시\s*오릅니다",
                    r"무조건\s*올라",
                    r"수익\s*확정",
                ],
                "description": "불확실한 수익을 확정적으로 표현",
                "law_reference": "금융소비자보호법 제22조 (부당권유 금지)"
            },
            {
                "id": "R003",
                "name": "개인정보 무단 수집 표현",
                "severity": "HIGH",
                "patterns": [
                    r"동의\s*없이.{0,20}수집",
                    r"모든\s*거래내역을\s*활용",
                    r"개인정보를\s*제3자에게",
                    r"동의\s*없이.{0,20}제공",
                ],
                "description": "동의 없는 개인정보 수집·활용 표현",
                "law_reference": "개인정보보호법 제15조 (개인정보 수집·이용)"
            },
            {
                "id": "R004",
                "name": "투자 손실 위험 미고지",
                "severity": "HIGH",
                "patterns": [
                    r"위험\s*없는\s*투자",
                    r"리스크\s*제로",
                    r"손실\s*위험이\s*없",
                ],
                "description": "투자 상품의 손실 위험성 미고지",
                "law_reference": "금융소비자보호법 제19조 (설명의무)"
            },

            # ==========================================
            # MEDIUM - 검토 필요
            # ==========================================
            {
                "id": "R005",
                "name": "비교 광고 근거 미제시",
                "severity": "MEDIUM",
                "patterns": [
                    r"업계\s*최고",
                    r"최저\s*금리",
                    r"최고\s*수익률",
                    r"국내\s*1위",
                    r"업계\s*유일",
                ],
                "description": "비교 우위 표현 시 객관적 근거 미제시",
                "law_reference": "금융소비자보호법 제22조 (부당권유 금지)"
            },
            {
                "id": "R006",
                "name": "필수 고지사항 누락 의심",
                "severity": "MEDIUM",
                "patterns": [
                    r"투자하세요(?!.{0,100}원금)",
                    r"가입하세요(?!.{0,100}위험)",
                    r"지금\s*바로\s*신청",
                ],
                "description": "투자 권유 시 위험고지 누락 가능성",
                "law_reference": "금융소비자보호법 제19조 (설명의무)"
            },
            {
                "id": "R007",
                "name": "개인신용정보 언급",
                "severity": "MEDIUM",
                "patterns": [
                    r"신용등급을\s*활용",
                    r"신용정보\s*조회",
                    r"금융거래\s*정보\s*수집",
                ],
                "description": "개인신용정보 처리 관련 동의 절차 확인 필요",
                "law_reference": "신용정보법 제32조 (개인신용정보 제공·활용 동의)"
            },
            {
                "id": "R008",
                "name": "긴급성·희소성 과장",
                "severity": "MEDIUM",
                "patterns": [
                    r"지금만\s*가능",
                    r"오늘까지만",
                    r"선착순\s*마감",
                    r"한정\s*특가",
                ],
                "description": "소비자 판단을 저해하는 긴급성·희소성 과장 표현",
                "law_reference": "금융소비자보호법 제21조 (불공정 영업행위 금지)"
            },

            # ==========================================
            # LOW - 모니터링
            # ==========================================
            {
                "id": "R009",
                "name": "애매한 수익률 표현",
                "severity": "LOW",
                "patterns": [
                    r"높은\s*수익",
                    r"좋은\s*수익률",
                    r"수익률이\s*좋",
                ],
                "description": "구체적 수치 없는 모호한 수익률 표현",
                "law_reference": "금융소비자보호법 제22조 참고"
            },
            {
                "id": "R010",
                "name": "전문용어 미설명",
                "severity": "LOW",
                "patterns": [
                    r"ELS(?!\s*\()",
                    r"DLS(?!\s*\()",
                    r"ETF(?!\s*\()",
                    r"ELB(?!\s*\()",
                ],
                "description": "금융 전문용어 사용 시 설명 누락",
                "law_reference": "금융소비자보호법 제19조 (설명의무)"
            },
        ]

    def analyze(self, content: str) -> List[RuleViolation]:
        """콘텐츠 분석 후 위반 목록 반환"""
        violations = []

        for rule in self.rules:
            for pattern in rule["patterns"]:
                matches = re.finditer(pattern, content)
                for match in matches:
                    # 앞뒤 30자 컨텍스트 추출
                    start = max(0, match.start() - 30)
                    end = min(len(content), match.end() + 30)
                    context = content[start:end]

                    violations.append(RuleViolation(
                        rule_id=rule["id"],
                        rule_name=rule["name"],
                        severity=rule["severity"],
                        flagged_text=context,
                        description=rule["description"],
                        law_reference=rule["law_reference"]
                    ))
                    break  # 같은 규칙 중복 방지

        return violations

    def get_severity_summary(self, violations: List[RuleViolation]) -> dict:
        """위반 심각도 요약"""
        summary = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for v in violations:
            summary[v.severity] += 1
        return summary


if __name__ == "__main__":
    # 테스트
    engine = RuleEngine()

    test_content = """
    이 상품은 원금 보장되는 고수익 투자 상품입니다.
    업계 최고의 수익률을 자랑하며, 손실 위험이 전혀 없습니다.
    지금만 가입 가능한 한정 특가 상품이니 지금 바로 신청하세요.
    고객님의 모든 거래내역을 활용하여 맞춤 서비스를 제공합니다.
    """

    print("=== Rule Engine 테스트 ===")
    violations = engine.analyze(test_content)

    for v in violations:
        print(f"\n[{v.severity}] {v.rule_name}")
        print(f"  탐지 문구: ...{v.flagged_text}...")
        print(f"  설명: {v.description}")
        print(f"  근거: {v.law_reference}")

    summary = engine.get_severity_summary(violations)
    print(f"\n📊 요약: HIGH {summary['HIGH']}건 | MEDIUM {summary['MEDIUM']}건 | LOW {summary['LOW']}건")
