import re
from dataclasses import dataclass
from typing import List, Tuple
from datetime import datetime
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "regRadar.db"

@dataclass
class InjectionResult:
    is_suspicious: bool
    threat_level: str      # HIGH / MEDIUM / LOW / SAFE
    detected_patterns: List[str]
    blocked: bool
    reason: str

class InjectionDetector:
    def __init__(self):
        self._init_log_db()
        self.patterns = self._load_patterns()

    def _init_log_db(self):
        """보안 로그 테이블 초기화"""
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS security_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_preview TEXT,
                threat_level TEXT,
                detected_patterns TEXT,
                blocked INTEGER,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _load_patterns(self):
        return {
            "HIGH": [
                # 역할 변경 시도
                r"당신은\s*이제.*(?:악의적|해킹|탈옥|jailbreak)",
                r"ignore\s*(?:all\s*)?(?:previous|prior)\s*instructions",
                r"forget\s*(?:all\s*)?(?:previous|prior)\s*instructions",
                r"you\s*are\s*now\s*(?:DAN|evil|unrestricted)",
                r"새로운\s*지시\s*따르",
                r"이전\s*지시\s*무시",
                r"시스템\s*프롬프트\s*무시",
                r"모든\s*규칙\s*무시",
                # 탈옥 시도
                r"DAN\s*mode",
                r"developer\s*mode",
                r"jailbreak",
                r"탈옥\s*모드",
                r"제한\s*없이\s*답변",
                # 시스템 명령 주입
                r"<\s*system\s*>",
                r"\[SYSTEM\]",
                r"```\s*system",
            ],
            "MEDIUM": [
                # 역할 변경
                r"당신은\s*(?:이제|사실|실제로)\s*준법\s*심의\s*(?:안|하지\s*마)",
                r"위반\s*(?:아님|없음|없다고)\s*판단",
                r"승인\s*(?:해줘|해주세요|하세요)",
                r"통과\s*(?:시켜|해줘)",
                r"심의\s*(?:없이|건너뛰고|패스)",
                # 우회 시도
                r"(?:규정|규칙|법령)\s*(?:무시|적용\s*하지\s*마|빼고)",
                r"그냥\s*(?:통과|승인|패스)",
                r"문제\s*없다고\s*해줘",
                # 프롬프트 확인 시도
                r"시스템\s*프롬프트\s*(?:알려줘|보여줘|출력)",
                r"your\s*(?:system\s*)?prompt",
                r"내부\s*지시\s*(?:알려줘|보여줘)",
                # 우회 표현 추가
                r"예외적으로\s*(?:통과|승인|허용)",
                r"이번만\s*(?:통과|승인|패스)",
                r"그냥\s*(?:괜찮|문제\s*없|통과)",
                r"(?:법적으로|규정상)\s*문제\s*없",
                r"심의\s*결과\s*(?:바꿔|수정|변경)",
                r"(?:안전|정상|무해)하다고\s*판단",
                r"위반\s*사항\s*없다고",
                r"통과\s*(?:가능|시켜|해줘)",
            ],
            "LOW": [
                # 의심스러운 표현
                r"심의\s*결과\s*바꿔",
                r"다시\s*판단\s*해줘",
                r"위반\s*없는\s*것으로",
                r"안전하다고\s*해줘",
                r"괜찮다고\s*해줘",
            ]
        }

    def detect(self, content: str) -> InjectionResult:
        """프롬프트 인젝션 탐지"""
        detected = []
        threat_level = "SAFE"
        blocked = False

        # HIGH 패턴 검사
        for pattern in self.patterns["HIGH"]:
            if re.search(pattern, content, re.IGNORECASE):
                detected.append(f"[HIGH] {pattern}")
                threat_level = "HIGH"
                blocked = True

        # MEDIUM 패턴 검사
        if threat_level != "HIGH":
            for pattern in self.patterns["MEDIUM"]:
                if re.search(pattern, content, re.IGNORECASE):
                    detected.append(f"[MEDIUM] {pattern}")
                    threat_level = "MEDIUM"

        # LOW 패턴 검사
        if threat_level == "SAFE":
            for pattern in self.patterns["LOW"]:
                if re.search(pattern, content, re.IGNORECASE):
                    detected.append(f"[LOW] {pattern}")
                    threat_level = "LOW"

        is_suspicious = threat_level != "SAFE"

        reason_map = {
            "HIGH": "심의 시스템 무력화 시도 탐지 — 요청 차단",
            "MEDIUM": "심의 결과 조작 시도 의심 — 보안 모니터링 중",
            "LOW": "비정상적 표현 감지 — 주의 요망",
            "SAFE": "정상 요청"
        }

        # 보안 로그 저장
        if is_suspicious:
            self._save_log(content[:100], threat_level, detected, blocked)

        return InjectionResult(
            is_suspicious=is_suspicious,
            threat_level=threat_level,
            detected_patterns=detected,
            blocked=blocked,
            reason=reason_map[threat_level]
        )

    def _save_log(self, content_preview: str, threat_level: str,
                  patterns: List[str], blocked: bool):
        """보안 이벤트 로그 저장"""
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO security_logs
            (content_preview, threat_level, detected_patterns, blocked, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            content_preview,
            threat_level,
            str(patterns),
            1 if blocked else 0,
            datetime.now().isoformat()
        ))
        conn.commit()
        conn.close()

    def get_security_logs(self, limit: int = 20) -> List[dict]:
        """보안 로그 조회"""
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, content_preview, threat_level,
                   detected_patterns, blocked, created_at
            FROM security_logs
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": r[0],
                "content_preview": r[1],
                "threat_level": r[2],
                "detected_patterns": r[3],
                "blocked": bool(r[4]),
                "created_at": r[5]
            }
            for r in rows
        ]

    def get_stats(self) -> dict:
        """보안 통계"""
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM security_logs")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM security_logs WHERE threat_level='HIGH'")
        high = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM security_logs WHERE blocked=1")
        blocked = cursor.fetchone()[0]
        conn.close()
        return {"total": total, "high": high, "blocked": blocked}
