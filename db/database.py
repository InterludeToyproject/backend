import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "regRadar.db"

class Database:
    def __init__(self):
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(str(DB_PATH))

    def _init_db(self):
        """테이블 초기화"""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                content_type TEXT,
                author TEXT,
                overall_risk TEXT,
                violations TEXT,
                suggestions TEXT,
                summary TEXT,
                pii_detected TEXT,
                approved TEXT DEFAULT 'PENDING',
                reviewer TEXT,
                reviewer_comment TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)

        conn.commit()
        conn.close()

    def save_review(self, content, content_type, author,
                    overall_risk, violations, suggestions,
                    summary, pii_detected) -> int:
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO reviews
            (content, content_type, author, overall_risk,
             violations, suggestions, summary, pii_detected,
             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            content, content_type, author, overall_risk,
            json.dumps(violations, ensure_ascii=False),
            json.dumps(suggestions, ensure_ascii=False),
            summary,
            json.dumps(pii_detected, ensure_ascii=False),
            now, now
        ))

        review_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return review_id

    def update_approval(self, review_id, action, reviewer, comment):
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        status = "APPROVED" if action == "approve" else "REJECTED"

        cursor.execute("""
            UPDATE reviews
            SET approved=?, reviewer=?, reviewer_comment=?, updated_at=?
            WHERE id=?
        """, (status, reviewer, comment, now, review_id))

        conn.commit()
        conn.close()

    def get_reviews(self, limit=20):
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, content_type, author, overall_risk,
                   approved, created_at, summary
            FROM reviews
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": r[0],
                "content_type": r[1],
                "author": r[2],
                "overall_risk": r[3],
                "approved": r[4],
                "created_at": r[5],
                "summary": r[6]
            }
            for r in rows
        ]

    def get_review(self, review_id):
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM reviews WHERE id=?", (review_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "id": row[0],
            "content": row[1],
            "content_type": row[2],
            "author": row[3],
            "overall_risk": row[4],
            "violations": json.loads(row[5]) if row[5] else [],
            "suggestions": json.loads(row[6]) if row[6] else [],
            "summary": row[7],
            "pii_detected": json.loads(row[8]) if row[8] else [],
            "approved": row[9],
            "reviewer": row[10],
            "reviewer_comment": row[11],
            "created_at": row[12],
            "updated_at": row[13]
        }

    def get_stats(self):
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM reviews")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM reviews WHERE approved='PENDING'")
        pending = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM reviews WHERE approved='APPROVED'")
        approved = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM reviews WHERE approved='REJECTED'")
        rejected = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM reviews WHERE overall_risk='HIGH'")
        high_risk = cursor.fetchone()[0]

        conn.close()

        return {
            "total": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "high_risk": high_risk
        }
