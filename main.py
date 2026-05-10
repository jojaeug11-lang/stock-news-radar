from datetime import datetime
from urllib.parse import quote_plus

import feedparser
from fastapi import FastAPI, Query

app = FastAPI(title="Stock News GPT Summary API", version="1.0.0")


POSITIVE_WORDS = [
    "상승", "강세", "급등", "호재", "수주", "계약", "공급", "실적",
    "흑자", "성장", "개선", "확대", "돌파", "매수", "기대",
    "회복", "증가", "최대", "승인", "협력", "투자"
]

NEGATIVE_WORDS = [
    "하락", "약세", "급락", "악재", "적자", "손실", "부진", "감소",
    "우려", "리콜", "소송", "논란", "압수수색", "규제", "매도",
    "위기", "중단", "철회", "불확실", "경고"
]

THEMES = {
    "실적": ["실적", "영업이익", "매출", "순이익", "흑자", "적자"],
    "수주/계약": ["수주", "계약", "공급", "납품"],
    "반도체": ["반도체", "HBM", "메모리", "AI칩", "파운드리"],
    "배터리": ["배터리", "2차전지", "양극재", "리튬"],
    "바이오": ["임상", "FDA", "신약", "승인", "바이오", "치료제"],
    "정책/규제": ["정부", "정책", "규제", "관세", "지원", "보조금"],
    "소송/리스크": ["소송", "압수수색", "논란", "리콜", "제재"],
    "증권사 의견": ["목표가", "매수", "투자의견", "리포트"],
    "M&A/투자": ["인수", "합병", "투자", "지분", "매각"],
}


def get_google_news(query: str, limit: int):
    encoded_query = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"

    feed = feedparser.parse(url)
    articles = []

    for entry in feed.entries[:limit]:
        source = ""
        if entry.get("source"):
            source = entry.get("source", {}).get("title", "")

        articles.append({
            "title": entry.get("title", ""),
            "source": source,
            "published": entry.get("published", "")
        })

    return articles


def find_words(text: str, words):
    return [word for word in words if word in text]


def find_themes(text: str):
    found = []

    for theme_name, keywords in THEMES.items():
        if any(keyword in text for keyword in keywords):
            found.append(theme_name)

    return found


def analyze_news(query: str, articles):
    analyzed = []
    positive_count = 0
    negative_count = 0
    all_themes = []
    positive_keywords = []
    negative_keywords = []

    for article in articles:
        title = article["title"]

        pos = find_words(title, POSITIVE_WORDS)
        neg = find_words(title, NEGATIVE_WORDS)
        themes = find_themes(title)

        positive_keywords.extend(pos)
        negative_keywords.extend(neg)
        all_themes.extend(themes)

        if len(pos) > len(neg):
            sentiment = "호재 가능성"
            positive_count += 1
        elif len(neg) > len(pos):
            sentiment = "악재 가능성"
            negative_count += 1
        else:
            sentiment = "중립"

        if themes:
            why = f"{', '.join(themes)} 관련 이슈라서 투자심리에 영향을 줄 수 있습니다."
        elif sentiment == "호재 가능성":
            why = "긍정적 표현이 포함되어 단기 관심을 받을 수 있습니다."
        elif sentiment == "악재 가능성":
            why = "부정적 표현이 포함되어 단기 변동성 요인이 될 수 있습니다."
        else:
            why = "제목만으로는 영향도를 강하게 판단하기 어렵습니다."

        analyzed.append({
            "title": title,
            "source": article["source"],
            "published": article["published"],
            "sentiment": sentiment,
            "themes": themes,
            "whyItMatters": why
        })

    if positive_count > negative_count:
        mood = "호재 우세"
        summary = f"{query} 관련 뉴스는 긍정적 표현이 상대적으로 많습니다."
    elif negative_count > positive_count:
        mood = "악재 우세"
        summary = f"{query} 관련 뉴스는 부정적 표현이 상대적으로 많습니다."
    elif positive_count > 0 and negative_count > 0:
        mood = "호재/악재 혼재"
        summary = f"{query} 관련 뉴스는 호재와 악재가 섞여 있습니다."
    else:
        mood = "중립"
        summary = f"{query} 관련 뉴스는 아직 뚜렷한 방향성이 약합니다."

    unique_themes = list(dict.fromkeys(all_themes))[:5]
    unique_positive = list(dict.fromkeys(positive_keywords))[:5]
    unique_negative = list(dict.fromkeys(negative_keywords))[:5]

    return {
        "mood": mood,
        "summary": summary,
        "positiveCount": positive_count,
        "negativeCount": negative_count,
        "keyThemes": unique_themes,
        "positiveFactors": unique_positive,
        "negativeFactors": unique_negative,
        "topNews": analyzed[:3]
    }


@app.get("/")
def home():
    return {
        "message": "Stock News GPT Summary API is running",
        "test": "/v1/news/gpt-summary?query=삼성전자"
    }


@app.get("/v1/news/gpt-summary")
def get_news_gpt_summary(
    query: str = Query(..., description="분석할 종목명입니다. 예: 삼성전자"),
    limit: int = Query(default=5, ge=3, le=8)
):
    articles = get_google_news(query, limit)
    result = analyze_news(query, articles)

    key_themes = ", ".join(result["keyThemes"]) if result["keyThemes"] else "뚜렷한 핵심 테마 없음"
    positive_factors = ", ".join(result["positiveFactors"]) if result["positiveFactors"] else "뚜렷한 긍정 키워드 없음"
    negative_factors = ", ".join(result["negativeFactors"]) if result["negativeFactors"] else "뚜렷한 부정 키워드 없음"

    news_lines = []

    for index, news in enumerate(result["topNews"], start=1):
        news_lines.append(
            f"{index}. {news['title']}\n"
            f"   - 출처: {news['source']}\n"
            f"   - 판단: {news['sentiment']}\n"
            f"   - 의미: {news['whyItMatters']}"
        )

    if not news_lines:
        news_lines.append("주요 뉴스를 찾지 못했습니다.")

    answer = f"""
[{query} 뉴스 인사이트]

1. 전체 분위기
- {result["mood"]}
- {result["summary"]}

2. 핵심 테마
- {key_themes}

3. 긍정 요인
- {positive_factors}

4. 부정/위험 요인
- {negative_factors}

5. 주요 뉴스와 의미
{chr(10).join(news_lines)}

6. 투자자가 확인할 점
- 뉴스 제목 기반 분석이므로 기사 원문, 공시, 실적 숫자를 함께 확인해야 합니다.
- 이 내용은 투자 참고용이며 매수·매도 추천이 아닙니다.
""".strip()

    return {
        "query": query,
        "generatedAt": datetime.now().isoformat(),
        "answer": answer
    }
