import re

def detect_language(text: str) -> str:
    """
    텍스트 언어 감지
    반환값: ko / en / zh / ja / other
    """
    # 한글 비율
    korean = len(re.findall(r'[가-힣]', text))
    # 영어 비율
    english = len(re.findall(r'[a-zA-Z]', text))
    # 중국어 비율
    chinese = len(re.findall(r'[\u4e00-\u9fff]', text))
    # 일본어 비율
    japanese = len(re.findall(r'[\u3040-\u30ff]', text))

    total = len(text.replace(" ", ""))
    if total == 0:
        return "ko"

    scores = {
        "ko": korean / total,
        "en": english / total,
        "zh": chinese / total,
        "ja": japanese / total,
    }

    dominant = max(scores, key=scores.get)

    # 한글이 20% 이상이면 한국어로 판단
    if scores["ko"] >= 0.2:
        return "ko"

    return dominant if scores[dominant] > 0.1 else "other"


LANGUAGE_NAMES = {
    "ko": "한국어",
    "en": "영어",
    "zh": "중국어",
    "ja": "일본어",
    "other": "기타"
}

LANGUAGE_FLAGS = {
    "ko": "🇰🇷",
    "en": "🇺🇸",
    "zh": "🇨🇳",
    "ja": "🇯🇵",
    "other": "🌐"
}
