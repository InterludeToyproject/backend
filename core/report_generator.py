import anthropic
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class ReportGenerator:
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
        self.model = "claude-sonnet-4-5"

    def generate_approval_report(self, review_data: dict) -> str:
        """승인 완료 레포트 생성"""
        prompt = f"""당신은 JB금융그룹 준법심의 시스템입니다.
아래 심의 완료된 콘텐츠에 대한 공식 승인 레포트를 작성하세요.

[심의 정보]
심의 번호: {review_data.get('review_id')}
콘텐츠 유형: {review_data.get('content_type')}
작성자: {review_data.get('author')}
심의자: {review_data.get('reviewer')}
심의 일시: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}
최종 위험도: {review_data.get('overall_risk')}
AI 신뢰도: {int(review_data.get('confidence', 0) * 100)}%

[심의 대상 콘텐츠]
{review_data.get('content', '')}

[AI 심의 요약]
{review_data.get('summary', '')}

[심의자 의견]
{review_data.get('comment', '없음')}

다음 형식으로 공식 준법심의 승인 레포트를 작성하세요:

# JB금융그룹 준법심의 승인 레포트

## 1. 심의 개요
(심의 번호, 일시, 담당자 등)

## 2. 콘텐츠 심의 결과
(AI 심의 결과 요약, 위험도, 신뢰도)

## 3. 준법 적합성 판단
(최종 승인 근거 및 판단 내용)

## 4. 배포 허가 조건
(특이사항 또는 조건부 승인 내용)

## 5. 서명
(심의자 확인)"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def generate_rejection_report(self, review_data: dict) -> str:
        """반려 레포트 + 수정 가이드 생성"""
        violations_str = "\n".join([
            f"- [{v.get('severity')}] {v.get('type')}: {v.get('flagged_text', '')[:50]}"
            for v in review_data.get('violations', [])
        ])

        suggestions_str = "\n".join([
            f"{i+1}. {s}"
            for i, s in enumerate(review_data.get('suggestions', []))
        ])

        prompt = f"""당신은 JB금융그룹 준법심의 시스템입니다.
아래 반려된 콘텐츠에 대한 공식 반려 레포트와 수정 가이드를 작성하세요.

[심의 정보]
심의 번호: {review_data.get('review_id')}
콘텐츠 유형: {review_data.get('content_type')}
작성자: {review_data.get('author')}
심의자: {review_data.get('reviewer')}
반려 일시: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}
최종 위험도: {review_data.get('overall_risk')}

[심의 대상 콘텐츠]
{review_data.get('content', '')}

[위반 항목]
{violations_str if violations_str else '없음'}

[AI 수정 제안]
{suggestions_str if suggestions_str else '없음'}

[심의자 반려 의견]
{review_data.get('comment', '없음')}

다음 형식으로 공식 준법심의 반려 레포트를 작성하세요:

# JB금융그룹 준법심의 반려 레포트

## 1. 반려 개요
(심의 번호, 일시, 담당자 등)

## 2. 반려 사유
(위반 항목별 구체적 사유 및 근거 법령)

## 3. 수정 필수 항목
(즉시 수정해야 할 항목 목록)

## 4. 수정 가이드
(항목별 구체적 수정 방향)

## 5. 재심의 요청 방법
(수정 후 재심의 절차 안내)

## 6. 서명
(심의자 확인)"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text
