import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List
import time

class RegulationCrawler:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        }
        self.sources = [
            {
                "name": "금융위원회",
                "url": "https://www.fsc.go.kr/po010101",
                "type": "fsc"
            },
            {
                "name": "개인정보보호위원회",
                "url": "https://www.pipc.go.kr/np/cop/bbs/selectBoardList.do?bbsId=BS217",
                "type": "pipc"
            },
            {
                "name": "금융감독원",
                "url": "https://www.fss.or.kr/fss/bbs/B0000188/list.do?menuNo=200218",
                "type": "fss"
            }
        ]

    def _parse_date(self, cols):
        """날짜 컬럼 자동 탐지"""
        for col in reversed(cols):
            text = col.get_text(strip=True)
            if len(text) <= 12 and ("." in text or "-" in text) and text[0].isdigit():
                return text
        return datetime.now().strftime("%Y.%m.%d")

    def crawl_fsc(self) -> List[dict]:
        """금융위원회 법령·규정 공시 크롤링"""
        results = []
        try:
            resp = requests.get(self.sources[0]["url"], headers=self.headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.select("table tbody tr")[:5]
            for row in rows:
                cols = row.select("td")
                if len(cols) >= 3:
                    title = cols[1].get_text(strip=True)
                    date = self._parse_date(cols)
                    link_tag = cols[1].find("a")
                    link = ""
                    if link_tag and link_tag.get("href"):
                        href = link_tag["href"]
                        link = f"https://www.fsc.go.kr{href}" if href.startswith("/") else href
                    if title:
                        results.append({"source": "금융위원회", "title": title, "date": date, "link": link, "type": "법령/규정"})
        except Exception as e:
            results.append({"source": "금융위원회", "title": f"크롤링 실패: {str(e)[:50]}", "date": datetime.now().strftime("%Y.%m.%d"), "link": self.sources[0]["url"], "type": "오류"})
        return results

    def crawl_pipc(self) -> List[dict]:
        """개인정보보호위원회 공시 크롤링"""
        results = []
        try:
            resp = requests.get(self.sources[1]["url"], headers=self.headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.select("table tbody tr")[:5]
            for row in rows:
                cols = row.select("td")
                if len(cols) >= 3:
                    title = cols[1].get_text(strip=True)
                    date = self._parse_date(cols)
                    link_tag = cols[1].find("a")
                    link = ""
                    if link_tag and link_tag.get("href"):
                        href = link_tag["href"]
                        link = f"https://www.pipc.go.kr{href}" if href.startswith("/") else href
                    if title:
                        results.append({"source": "개인정보보호위원회", "title": title, "date": date, "link": link, "type": "고시/공고"})
        except Exception as e:
            results.append({"source": "개인정보보호위원회", "title": f"크롤링 실패: {str(e)[:50]}", "date": datetime.now().strftime("%Y.%m.%d"), "link": self.sources[1]["url"], "type": "오류"})
        return results

    def crawl_fss(self) -> List[dict]:
        """금융감독원 규정 변경 크롤링"""
        results = []
        try:
            resp = requests.get(self.sources[2]["url"], headers=self.headers, timeout=10)
            soup = BeautifulSoup(resp.text, "html.parser")
            rows = soup.select("table tbody tr")[:5]
            for row in rows:
                cols = row.select("td")
                if len(cols) >= 3:
                    title = cols[1].get_text(strip=True)
                    date = self._parse_date(cols)
                    link_tag = cols[1].find("a")
                    link = ""
                    if link_tag and link_tag.get("href"):
                        href = link_tag["href"]
                        link = f"https://www.fss.or.kr{href}" if href.startswith("/") else href
                    if title:
                        results.append({"source": "금융감독원", "title": title, "date": date, "link": link, "type": "규정"})
        except Exception as e:
            results.append({"source": "금융감독원", "title": f"크롤링 실패: {str(e)[:50]}", "date": datetime.now().strftime("%Y.%m.%d"), "link": self.sources[2]["url"], "type": "오류"})
        return results

    def crawl_all(self) -> List[dict]:
        """전체 크롤링"""
        results = []
        results.extend(self.crawl_fsc())
        time.sleep(1)
        results.extend(self.crawl_pipc())
        time.sleep(1)
        results.extend(self.crawl_fss())
        results.sort(key=lambda x: x.get("date", ""), reverse=True)
        return results

    def analyze_relevance(self, items: List[dict]) -> List[dict]:
        """준법심의 관련 여부 분류"""
        keywords = [
            "개인정보", "금융소비자", "광고", "마케팅", "불완전판매",
            "신용정보", "전자금융", "약관", "공시", "수익률", "원금",
            "투자", "보장", "규제", "고시", "시행령", "감독규정"
        ]
        for item in items:
            title = item.get("title", "")
            relevance_score = sum(1 for kw in keywords if kw in title)
            if relevance_score >= 2:
                item["relevance"] = "HIGH"
                item["relevance_label"] = "🔴 즉시 검토 필요"
            elif relevance_score == 1:
                item["relevance"] = "MEDIUM"
                item["relevance_label"] = "🟡 검토 권장"
            else:
                item["relevance"] = "LOW"
                item["relevance_label"] = "🟢 참고"
        return items