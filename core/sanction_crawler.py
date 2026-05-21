import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List
import time

class SanctionCrawler:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        }
        self.base_url = "https://casenote.kr"
        self.sanction_url = "https://casenote.kr/%EA%B8%88%EC%9C%B5%EA%B0%90%EB%8F%85%EC%9B%90/%EC%A0%9C%EC%9E%AC/"

    def crawl_sanctions(self) -> List[dict]:
        """casenote.kr 금감원 제재 사례 크롤링"""
        results = []
        try:
            resp = requests.get(
                self.sanction_url,
                headers=self.headers,
                timeout=10
            )
            soup = BeautifulSoup(resp.text, "html.parser")

            # 제재 목록 파싱
            items = soup.select("a.case-item, div.case-list a, ul.list li a, .search-result a")

            # 일반적인 링크 파싱으로 폴백
            if not items:
                items = soup.select("a[href*='제재']")

            if not items:
                # 텍스트 기반 파싱
                all_links = soup.find_all("a", href=True)
                for link in all_links:
                    text = link.get_text(strip=True)
                    href = link.get("href", "")
                    if len(text) > 10 and ("제재" in text or "과태료" in text or "기관경고" in text or "은행" in text or "증권" in text):
                        full_url = f"{self.base_url}{href}" if href.startswith("/") else href
                        results.append({
                            "title": text[:80],
                            "date": datetime.now().strftime("%Y.%m.%d"),
                            "link": full_url,
                            "source": "금융감독원 제재"
                        })

            for item in items[:10]:
                text = item.get_text(strip=True)
                href = item.get("href", "")
                if text and len(text) > 5:
                    full_url = f"{self.base_url}{href}" if href.startswith("/") else href
                    results.append({
                        "title": text[:80],
                        "date": datetime.now().strftime("%Y.%m.%d"),
                        "link": full_url,
                        "source": "금융감독원 제재"
                    })

        except Exception as e:
            print(f"제재 크롤링 실패: {e}")

        return results[:10]

    def find_relevant_sanctions(self, violation_types: List[str]) -> List[dict]:
        """위반 유형과 관련된 제재 사례 검색"""
        all_sanctions = self.crawl_sanctions()

        if not all_sanctions:
            # 크롤링 실패 시 금감원 제재 페이지 직접 링크 제공
            return self._get_fallback_cases(violation_types)

        keywords_map = {
            "광고": ["광고", "홍보", "마케팅"],
            "개인정보": ["개인정보", "정보"],
            "불완전판매": ["불완전", "설명"],
            "원금": ["손실", "원금", "보장"],
            "금리": ["금리", "이자"],
            "보험": ["보험"],
            "투자": ["투자", "펀드", "증권"],
        }

        relevant = []
        for sanction in all_sanctions:
            title = sanction.get("title", "")
            for vtype in violation_types:
                for keyword, search_terms in keywords_map.items():
                    if keyword in vtype:
                        if any(term in title for term in search_terms):
                            sanction["relevance"] = keyword
                            if sanction not in relevant:
                                relevant.append(sanction)
                            break

        # 매칭 없으면 전체에서 상위 2개
        if not relevant and all_sanctions:
            relevant = all_sanctions[:2]

        return relevant[:3]

    def _get_fallback_cases(self, violation_types: List[str]) -> List[dict]:
        """크롤링 실패 시 금감원 제재 검색 링크 제공"""
        cases = []
        for vtype in violation_types[:2]:
            keyword = vtype[:10]
            search_url = f"https://casenote.kr/%EA%B8%88%EC%9C%B5%EA%B0%90%EB%8F%85%EC%9B%90/%EC%A0%9C%EC%9E%AC/"
            cases.append({
                "title": f"금감원 '{keyword}' 관련 제재 사례 검색",
                "date": datetime.now().strftime("%Y.%m.%d"),
                "link": search_url,
                "source": "금융감독원 제재"
            })
        return cases