import re
from typing import List

def highlight_content(content: str, violations: List[dict], rule_violations: List) -> str:
    """
    위반 문구를 HTML 하이라이팅으로 표시
    HIGH → 빨간색, MEDIUM → 주황색, LOW → 노란색
    """
    highlighted = content

    color_map = {
        "HIGH":   "#FFB3B3",  # 빨간색
        "MEDIUM": "#FFD9B3",  # 주황색
        "LOW":    "#FFFAB3",  # 노란색
    }
    border_map = {
        "HIGH":   "#FF0000",
        "MEDIUM": "#FF8C00",
        "LOW":    "#FFD700",
    }

    # 위반 문구 수집 (AI 판단 결과)
    targets = []
    for v in violations:
        flagged = v.get("flagged_text", "").strip()
        severity = v.get("severity", "MEDIUM")
        if flagged and flagged != "전체 콘텐츠" and len(flagged) > 2:
            targets.append({"text": flagged, "severity": severity, "source": "AI"})

    # Rule Engine 결과 추가
    for v in rule_violations:
        flagged = v.flagged_text.strip()
        if flagged and len(flagged) > 2:
            targets.append({"text": flagged[:30], "severity": v.severity, "source": "Rule"})

    # 중복 제거 + 긴 것 먼저 처리 (짧은 게 먼저면 겹침 발생)
    targets.sort(key=lambda x: len(x["text"]), reverse=True)
    seen = set()
    unique_targets = []
    for t in targets:
        key = t["text"][:20]
        if key not in seen:
            seen.add(key)
            unique_targets.append(t)

    # HTML 태그로 감싸기
    for t in unique_targets:
        text = t["text"]
        severity = t["severity"]
        bg = color_map.get(severity, "#FFFAB3")
        border = border_map.get(severity, "#FFD700")

        # 실제 콘텐츠에서 해당 문구 찾아서 치환
        # 앞 10자 기준으로 매칭
        search_text = text[:25] if len(text) > 25 else text

        if search_text in highlighted:
            replacement = (
                f'<mark style="background-color:{bg};'
                f'border-bottom:2px solid {border};'
                f'padding:1px 3px;border-radius:3px;'
                f'font-weight:bold;" '
                f'title="{severity} 위반">'
                f'{search_text}</mark>'
            )
            highlighted = highlighted.replace(search_text, replacement, 1)

    return highlighted


def render_highlighted_content(highlighted_html: str, violations: List[dict]) -> str:
    """
    하이라이팅된 HTML + 범례 생성
    """
    legend = """
    <div style="margin-bottom:10px;padding:8px;background:#f8f9fa;border-radius:5px;font-size:12px;">
        <b>범례:</b>
        <span style="background:#FFB3B3;border-bottom:2px solid #FF0000;padding:1px 6px;margin:0 5px;border-radius:3px;">🔴 HIGH</span>
        <span style="background:#FFD9B3;border-bottom:2px solid #FF8C00;padding:1px 6px;margin:0 5px;border-radius:3px;">🟠 MEDIUM</span>
        <span style="background:#FFFAB3;border-bottom:2px solid #FFD700;padding:1px 6px;margin:0 5px;border-radius:3px;">🟡 LOW</span>
    </div>
    """

    content_html = f"""
    <div style="
        background:white;
        border:1px solid #ddd;
        border-radius:8px;
        padding:20px;
        font-size:15px;
        line-height:1.8;
        white-space:pre-wrap;
        font-family:'맑은 고딕', sans-serif;
    ">
        {highlighted_html}
    </div>
    """

    return legend + content_html
