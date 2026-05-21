import json
import os
import sqlite3
from pathlib import Path
import anthropic
from dotenv import load_dotenv
from core.rag import load_vectorstore

load_dotenv()

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "regRadar.db"

class RuleExtractor:
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self.model = "claude-sonnet-4-5"
        self._init_rule_db()

    def _init_rule_db(self):
        """동적 규칙 테이블 초기화"""
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dynamic_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id TEXT UNIQUE,
                rule_name TEXT,
                severity TEXT,
                patterns TEXT,
                description TEXT,
                law_reference TEXT,
                source_law TEXT,
                created_at TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)
        conn.commit()
        conn.close()

    def extract_rules_from_law(self, law_name: str, law_content: str) -> list:
        """규제 조문에서 규칙 자동 추출"""
        prompt = f"""당신은 금융 준법심의 전문가입니다.
아래 규제 조문을 분석하여 마케팅 콘텐츠 심의에 사용할 수 있는 규칙을 추출하세요.

[규제 조문]
{law_content[:2000]}

다음 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만 출력하세요:
{{
    "rules": [
        {{
            "rule_name": "규칙 이름 (간결하게)",
            "severity": "HIGH 또는 MEDIUM 또는 LOW",
            "patterns": ["탐지할 키워드 또는 표현 패턴 1", "패턴 2"],
            "description": "위반 설명",
            "law_reference": "법령명 조항"
        }}
    ]
}}

주의사항:
- 실제로 마케팅 콘텐츠에서 자주 나타날 수 있는 패턴만 추출
- 패턴은 2~5개의 구체적인 표현으로 작성
- 최대 5개 규칙만 추출
- 반드시 JSON만 출력"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.content[0].text.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()

        result = json.loads(raw)
        return result.get("rules", [])

    def extract_from_vectorstore(self, queries: list) -> int:
        """벡터스토어에서 규제 내용 검색 후 규칙 추출"""
        from core.rag import search_regulations
        from datetime import datetime

        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        total_added = 0

        for query in queries:
            results = search_regulations(query, k=3)

            for result in results:
                law_name = result.get("law_name", "")
                content = result.get("content", "")

                if len(content) < 50:
                    continue

                try:
                    rules = self.extract_rules_from_law(law_name, content)

                    for i, rule in enumerate(rules):
                        rule_id = f"AUTO_{law_name[:10]}_{query[:5]}_{i}"
                        rule_id = rule_id.replace(" ", "_").replace("/", "_")

                        patterns_json = json.dumps(
                            rule.get("patterns", []),
                            ensure_ascii=False
                        )

                        cursor.execute("""
                            INSERT OR IGNORE INTO dynamic_rules
                            (rule_id, rule_name, severity, patterns,
                             description, law_reference, source_law, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            rule_id,
                            rule.get("rule_name", ""),
                            rule.get("severity", "MEDIUM"),
                            patterns_json,
                            rule.get("description", ""),
                            rule.get("law_reference", ""),
                            law_name,
                            datetime.now().isoformat()
                        ))

                        if cursor.rowcount > 0:
                            total_added += 1

                except Exception as e:
                    print(f"규칙 추출 실패: {e}")
                    continue

        conn.commit()
        conn.close()
        return total_added

    def get_dynamic_rules(self) -> list:
        """DB에서 동적 규칙 조회"""
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rule_id, rule_name, severity, patterns,
                   description, law_reference, source_law
            FROM dynamic_rules
            WHERE is_active = 1
        """)
        rows = cursor.fetchall()
        conn.close()

        rules = []
        for row in rows:
            try:
                patterns = json.loads(row[3])
                rules.append({
                    "id": row[0],
                    "name": row[1],
                    "severity": row[2],
                    "patterns": patterns,
                    "description": row[4],
                    "law_reference": row[5],
                    "source_law": row[6]
                })
            except:
                continue
        return rules

    def get_stats(self) -> dict:
        """규칙 통계"""
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM dynamic_rules WHERE is_active = 1")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM dynamic_rules WHERE severity='HIGH' AND is_active=1")
        high = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM dynamic_rules WHERE severity='MEDIUM' AND is_active=1")
        medium = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM dynamic_rules WHERE severity='LOW' AND is_active=1")
        low = cursor.fetchone()[0]
        conn.close()
        return {"total": total, "high": high, "medium": medium, "low": low}
