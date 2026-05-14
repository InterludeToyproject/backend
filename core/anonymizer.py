import re
from dataclasses import dataclass
from typing import Tuple

@dataclass
class AnonymizationResult:
    anonymized_text: str      # 마스킹된 텍스트
    token_map: dict           # 복원용 매핑 테이블
    detected_pii: list        # 탐지된 개인정보 목록

class Anonymizer:
    def __init__(self):
        self.token_counter = 0
        self.patterns = self._load_patterns()

    def _load_patterns(self):
        return [
            # 주민등록번호
            {
                "id": "PII001",
                "name": "주민등록번호",
                "pattern": r"\d{6}-[1-4]\d{6}",
                "token": "RESIDENT_ID"
            },
            # 휴대폰번호
            {
                "id": "PII004",
                "name": "휴대폰번호",
                "pattern": r"01[016789]-\d{3,4}-\d{4}",
                "token": "MOBILE_NUM"
            },
            # 전화번호
            {
                "id": "PII003",
                "name": "전화번호",
                "pattern": r"0\d{1,2}-\d{3,4}-\d{4}",
                "token": "PHONE_NUM"
            },
            # 계좌번호
            {
                "id": "PII002",
                "name": "계좌번호",
                "pattern": r"\d{3,6}-\d{2,6}-\d{2,6}(-\d{2})?",
                "token": "ACCOUNT_NUM"
            },
            # 이메일
            {
                "id": "PII005",
                "name": "이메일",
                "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                "token": "EMAIL"
            },
            # 카드번호
            {
                "id": "PII006",
                "name": "카드번호",
                "pattern": r"\d{4}-\d{4}-\d{4}-\d{4}",
                "token": "CARD_NUM"
            },
            # 여권번호
            {
                "id": "PII007",
                "name": "여권번호",
                "pattern": r"[A-Z]{1}\d{8}",
                "token": "PASSPORT_NUM"
            },
            # IP 주소
            {
                "id": "PII008",
                "name": "IP주소",
                "pattern": r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",
                "token": "IP_ADDR"
            },
        ]

    def anonymize(self, text: str) -> AnonymizationResult:
        """텍스트 익명화 처리"""
        anonymized = text
        token_map = {}
        detected_pii = []
        self.token_counter = 0

        for pii in self.patterns:
            matches = list(re.finditer(pii["pattern"], anonymized))

            for match in matches:
                original = match.group()
                token_key = f"<{pii['token']}_{self.token_counter}>"
                self.token_counter += 1

                token_map[token_key] = original
                anonymized = anonymized.replace(original, token_key, 1)

                detected_pii.append({
                    "type": pii["name"],
                    "original": original[:4] + "****",  # 앞 4자리만 표시
                    "token": token_key
                })

        return AnonymizationResult(
            anonymized_text=anonymized,
            token_map=token_map,
            detected_pii=detected_pii
        )

    def restore(self, anonymized_text: str, token_map: dict) -> str:
        """토큰 복원"""
        restored = anonymized_text
        for token, original in token_map.items():
            restored = restored.replace(token, original)
        return restored

    def is_safe_to_send(self, text: str) -> Tuple[bool, list]:
        """
        외부 API 전송 전 안전 여부 확인
        개인정보 포함 시 False 반환
        """
        result = self.anonymize(text)
        is_safe = len(result.detected_pii) == 0
        return is_safe, result.detected_pii


if __name__ == "__main__":
    anonymizer = Anonymizer()

    test_content = """
    고객 홍길동(010-1234-5678)님의 계좌번호 110-123-456789로
    투자 상품 안내 문자를 발송합니다.
    이메일: hong@example.com
    주민번호: 800101-1234567
    이 상품은 원금 보장되는 고수익 상품입니다.
    """

    print("=== 익명화 테스트 ===")
    print(f"\n원본:\n{test_content}")

    result = anonymizer.anonymize(test_content)

    print(f"\n익명화 결과:\n{result.anonymized_text}")
    print(f"\n탐지된 개인정보:")
    for pii in result.detected_pii:
        print(f"  [{pii['type']}] {pii['original']} → {pii['token']}")

    print(f"\n복원 결과:\n{anonymizer.restore(result.anonymized_text, result.token_map)}")

    is_safe, detected = anonymizer.is_safe_to_send(test_content)
    print(f"\n외부 API 전송 안전 여부: {'✅ 안전' if is_safe else '❌ 위험 (개인정보 포함)'}")

