import re
from dataclasses import dataclass
from typing import List

@dataclass
class RuleViolation:
    rule_id: str
    rule_name: str
    severity: str
    flagged_text: str
    description: str
    law_reference: str

class RuleEngine:
    def __init__(self):
        self.rules = self._load_rules()
        self._load_dynamic_rules()

    def _load_dynamic_rules(self):
        """DB에서 동적 규칙 로드"""
        try:
            from core.rule_extractor import RuleExtractor
            extractor = RuleExtractor()
            dynamic = extractor.get_dynamic_rules()
            for rule in dynamic:
                self.rules.append({
                    "id": rule["id"],
                    "name": rule["name"],
                    "severity": rule["severity"],
                    "patterns": rule["patterns"],
                    "description": rule["description"],
                    "law_reference": rule["law_reference"]
                })
        except Exception as e:
            print(f"동적 규칙 로드 실패: {e}")

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
            {
                "id": "R011",
                "name": "수익률 과거 실적 미고지",
                "severity": "HIGH",
                "patterns": [
                    r"연\s*\d+%\s*수익",
                    r"\d+%\s*수익률\s*보장",
                    r"작년에\s*\d+%",
                ],
                "description": "과거 수익률 제시 시 미래 수익 미보장 문구 누락",
                "law_reference": "금융소비자보호법 제17조 (광고 필수 고지사항)"
            },
            {
                "id": "R012",
                "name": "투자 원금 손실 위험 미고지",
                "severity": "HIGH",
                "patterns": [
                    r"절대\s*손실\s*없",
                    r"무조건\s*이익",
                    r"반드시\s*수익",
                ],
                "description": "투자성 상품 광고 시 원금 손실 가능성 미고지",
                "law_reference": "금융소비자보호법 제19조 (설명의무)"
            },
            {
                "id": "R014",
                "name": "약관 불공정 조항 표현",
                "severity": "HIGH",
                "patterns": [
                    r"일방적으로\s*변경",
                    r"고객\s*동의\s*없이\s*수정",
                    r"회사\s*재량으로\s*변경",
                ],
                "description": "약관의 일방적 변경 가능성을 시사하는 불공정 조항",
                "law_reference": "금융소비자보호법 제14조 (약관 규제)"
            },
            {
                "id": "R015",
                "name": "대출 금리 과장",
                "severity": "HIGH",
                "patterns": [
                    r"초저금리",
                    r"업계\s*최저\s*금리",
                    r"금리\s*0%",
                    r"무이자\s*대출",
                ],
                "description": "대출 금리 과장 광고 또는 근거 없는 최저 금리 표현",
                "law_reference": "대부업법 제9조 (광고 규제)"
            },
            {
                "id": "R016",
                "name": "보험 보장 범위 과장",
                "severity": "HIGH",
                "patterns": [
                    r"모든\s*질병\s*보장",
                    r"100%\s*보장",
                    r"완벽한\s*보장",
                    r"전액\s*보상",
                ],
                "description": "보험 보장 범위 과장 표현",
                "law_reference": "보험업법 제95조 (보험광고 규제)"
            },
            {
                "id": "R017",
                "name": "개인정보 제3자 제공 미고지",
                "severity": "HIGH",
                "patterns": [
                    r"제휴사에\s*제공",
                    r"파트너사\s*공유",
                    r"협력업체.*전달",
                ],
                "description": "개인정보 제3자 제공 시 동의 절차 미고지",
                "law_reference": "개인정보보호법 제17조 (개인정보 제3자 제공)"
            },
            {
                "id": "R019",
                "name": "취약계층 대상 과장",
                "severity": "HIGH",
                "patterns": [
                    r"어린이.*투자",
                    r"노후\s*보장\s*완벽",
                    r"은퇴\s*후\s*걱정\s*없",
                    r"어르신.*무조건",
                ],
                "description": "취약계층 대상 과장·허위 광고",
                "law_reference": "금융소비자보호법 제21조 (불공정 영업행위)"
            },
            {
                "id": "R020",
                "name": "손실보전 약정 표현",
                "severity": "HIGH",
                "patterns": [
                    r"손실.*보전",
                    r"손실.*메워",
                    r"손실.*보상해",
                    r"마이너스.*보장",
                ],
                "description": "손실보전 약정 또는 이익보장 약정 표현",
                "law_reference": "자본시장법 제55조 (손실보전 등의 금지)"
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
            {
                "id": "R013",
                "name": "SNS 해시태그 과장 광고",
                "severity": "MEDIUM",
                "patterns": [
                    r"#수익인증",
                    r"#재테크성공",
                    r"#월\d+만",
                    r"#무조건수익",
                ],
                "description": "SNS 해시태그를 통한 과장 광고 표현",
                "law_reference": "금융소비자보호법 제22조 (부당권유 금지)"
            },
            {
                "id": "R018",
                "name": "AI 생성 콘텐츠 미표시",
                "severity": "MEDIUM",
                "patterns": [
                    r"AI\s*작성",
                    r"인공지능\s*생성",
                    r"ChatGPT",
                    r"자동\s*생성된",
                ],
                "description": "AI 생성 콘텐츠임을 명시하지 않고 배포하는 경우",
                "law_reference": "금융소비자보호법 제17조 (광고 표시 의무)"
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
                try:
                    matches = re.finditer(pattern, content)
                    for match in matches:
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
                        break
                except:
                    continue
        return violations

    def get_severity_summary(self, violations: List[RuleViolation]) -> dict:
        summary = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for v in violations:
            summary[v.severity] += 1
        return summary