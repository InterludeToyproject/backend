# RegRadar Backend

JB금융그룹 준법심의 AI Agent — FastAPI 백엔드

## 기술 스택

- Python 3.11
- FastAPI
- LangChain + ChromaDB (RAG)
- Claude Sonnet API (Anthropic)
- presidio-analyzer (개인정보 익명화)
- langdetect (다국어 감지)
- BeautifulSoup4 (규제 공시 크롤링)
- SQLite

## 프로젝트 구조
backend/

├── main.py                  # FastAPI 진입점

├── core/

│   ├── rag.py               # RAG 파이프라인

│   ├── rule_engine.py       # Rule Engine (정적 20개)

│   ├── rule_extractor.py    # 동적 규칙 자동 추출

│   ├── llm_provider.py      # Claude AI 판단 + 수정본 생성

│   ├── anonymizer.py        # 개인정보 익명화

│   ├── highlighter.py       # 위반 문구 하이라이팅

│   ├── hallucination_detector.py  # 환각 방지 조문 검증

│   ├── language_detector.py # 다국어 감지

│   ├── injection_detector.py # 프롬프트 인젝션 탐지

│   ├── penalty_calculator.py # 과태료 시뮬레이터

│   ├── report_generator.py  # 승인/반려 레포트 생성

│   └── crawler.py           # 규제 공시 크롤링

└── db/

└── database.py          # SQLite 이력 관리

## 설치 및 실행

### 1. 가상환경 생성 및 활성화

```bash
# Mac/Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 2. 패키지 설치

```bash
pip install -r requirements.txt
```

### 3. 환경변수 설정

루트 폴더에 `.env` 파일 생성

ANTHROPIC_API_KEY=sk-ant-여기에API키입력

LLM_PROVIDER=claude

### 4. 규제문서 준비

`data/regulations/` 폴더에 아래 PDF 7개 저장

- 개인정보 보호법
- 개인정보 보호법 시행령
- 금융소비자 보호에 관한 법률
- 금융소비자 보호에 관한 법률 시행령
- 신용정보의 이용 및 보호에 관한 법률
- 신용정보의 이용 및 보호에 관한 법률 시행령
- 전자금융감독규정

다운로드: https://www.law.go.kr

### 5. 벡터스토어 구축 (최초 1회)

```bash
cd backend
python3 core/rag.py
```

약 10~20분 소요 (모델 최초 다운로드)

### 6. 서버 실행

```bash
cd backend
uvicorn main:app --reload
```

서버 주소: http://127.0.0.1:8000

## API 엔드포인트

| Method | URL | 설명 |
|--------|-----|------|
| POST | /scan-content | 콘텐츠 준법 심의 |
| POST | /generate-correction | 수정본 자동 생성 |
| POST | /approve | 승인/반려 + 레포트 생성 |
| GET | /reviews | 심의 이력 조회 |
| GET | /stats | 대시보드 통계 |
| POST | /upload-regulation | 규제 변경 업로드 |
| POST | /retroactive-scan | 소급 위반 탐지 |
| GET | /crawl-regulations | 규제 공시 크롤링 |
| POST | /extract-rules | 동적 규칙 자동 추출 |
| GET | /security/logs | 보안 이벤트 로그 |

## 주의사항

- `.env` 파일은 절대 깃허브에 업로드하지 마세요
- `vectorstore/` 폴더는 `.gitignore`에 포함 (용량 큼)
- `data/regulations/` PDF는 별도 공유 필요
