from datetime import datetime
from urllib.parse import quote_plus

import feedparser
from fastapi import FastAPI, Query

app = FastAPI(title="Stock News Insight API", version="1.1.0")


POSITIVE_WORDS = [
    "상승", "강세", "급등", "호재", "수주", "계약", "공급", "실적",
    "흑자", "성장", "개선", "확대", "돌파", "매수", "기대",
    "회복", "증가", "최대", "신고가", "승인", "협력", "투자"
]

NEGATIVE_WORDS = [
    "하락", "약세", "급락", "악재", "적자", "손실", "부진", "감소",
    "우려", "리콜", "소송", "논란", "압수수색", "규제", "매도",
    "위기", "중단", "철회", "불확실", "경고"
]

THEME_MAP = {
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


def get_google_news(query: str, limit: int = 10):
    search_word = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={search_word}&hl=ko&gl=KR&ceid=KR:ko"

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


def find_keywords(text: str, words):
    return [word for word in words if word in text]


def detect_themes(text: str):
    themes = []

    for theme, keywords in THEME_MAP.items():
        if any(keyword in text for keyword in keywords):
            themes.append(theme)

    return themes


def explain_why(title: str, themes):
    if "실적" in themes:
        return "실적 전망과 기업가치 평가에 직접 연결될 수 있는 뉴스입니다."
    if "수주/계약" in themes:
        return "향후 매출 증가 기대와 연결될 수 있는 뉴스입니다."
    if "반도체" in themes:
        return "반도체 업황과 투자심리에 영향을 줄 수 있는 뉴스입니다."
    if "배터리" in themes:
        return "2차전지 업황과 관련주 투자심리에 영향을 줄 수 있습니다."
    if "바이오" in themes:
        return "임상, 승인, 신약 기대감은 주가 변동성을 키울 수 있습니다."
    if "정책/규제" in themes:
        return "정책이나 규제 변화는 업종 전체 분위기에 영향을 줄 수 있습니다."
    if "소송/리스크" in themes:
        return "기업 신뢰도와 단기 투자심리에 부정적 영향을 줄 수 있습니다."
    if "증권사 의견" in themes:
        return "증권사 목표가나 투자의견 변화는 단기 수급에 영향을 줄 수 있습니다."
    if "M&A/투자" in themes:
        return "사업구조 변화나 성장 기대감과 연결될 수 있습니다."

    if any(word in title for word in POSITIVE_WORDS):
        return "긍정적 표현이 포함되어 투자심리에 영향을 줄 수 있습니다."
    if any(word in title for word in NEGATIVE_WORDS):
        return "부정적 표현이 포함되어 단기 변동성 확대 요인이 될 수 있습니다."

    return "제목만으로는 영향도를 강하게 판단하기 어렵습니다."


def analyze_article(article):
    title = article.get("title", "")

    positive_hits = find_keywords(title, POSITIVE_WORDS)
    negative_hits = find_keywords(title, NEGATIVE_WORDS)
    themes = detect_themes(title)

    score = len(positive_hits) - len(negative_hits)

    if score > 0:
        sentiment = "positive"
        sentiment_label = "호재 가능성"
    elif score < 0:
        sentiment = "negative"
        sentiment_label = "악재 가능성"
    else:
        sentiment = "neutral"
        sentiment_label = "중립"

    importance = 1
    importance += min(2, len(themes))
    if positive_hits or negative_hits:
        importance += 1
    importance = min(5, importance)

    return {
        "title": title,
        "source": article.get("source", ""),
        "published": article.get("published", ""),
        "sentiment": sentiment,
        "sentimentLabel": sentiment_label,
        "importance": importance,
        "themes": themes,
        "positiveKeywords": positive_hits,
        "negativeKeywords": negative_hits,
        "whyItMatters": explain_why(title, themes)
    }


def make_risk_flags(analyzed_articles):
    flags = []

    negative_count = sum(1 for a in analyzed_articles if a["sentiment"] == "negative")
    positive_count = sum(1 for a in analyzed_articles if a["sentiment"] == "positive")
    all_titles = " ".join([a["title"] for a in analyzed_articles])

    if negative_count >= 2:
        flags.append({
            "type": "negative_news_cluster",
            "severity": "medium",
            "description": "악재성 표현이 포함된 뉴스가 여러 건 있습니다."
        })

    if "소송" in all_titles or "압수수색" in all_titles or "리콜" in all_titles:
        flags.append({
            "type": "legal_or_reputation_risk",
            "severity": "high",
            "description": "소송, 압수수색, 리콜 등 신뢰도에 영향을 줄 수 있는 키워드가 있습니다."
        })

    if "급등" in all_titles or "신고가" in all_titles:
        flags.append({
            "type": "priced_in_risk",
            "severity": "medium",
            "description": "이미 주가에 기대감이 일부 반영됐을 가능성이 있습니다."
        })

    if positive_count >= 2 and negative_count >= 1:
        flags.append({
            "type": "mixed_signal",
            "severity": "low",
            "description": "호재와 악재가 함께 나타나 방향성이 엇갈릴 수 있습니다."
        })

    return flags[:3]


def build_insight(query: str, articles, top_count: int = 5):
    analyzed = [analyze_article(article) for article in articles]

    positive_count = sum(1 for a in analyzed if a["sentiment"] == "positive")
    negative_count = sum(1 for a in analyzed if a["sentiment"] == "negative")

    score = 0
    for article in analyzed:
        if article["sentiment"] == "positive":
            score += article["importance"] * 10
        elif article["sentiment"] == "negative":
            score -= article["importance"] * 10

    score = max(-100, min(100, score))

    if positive_count > negative_count and positive_count >= 2:
        mood = "positive"
        mood_label = "호재 우세"
        one_line = f"{query} 관련 뉴스는 긍정적 재료가 더 많이 보입니다."
    elif negative_count > positive_count and negative_count >= 2:
        mood = "negative"
        mood_label = "악재 우세"
        one_line = f"{query} 관련 뉴스는 부정적 재료가 더 많이 보입니다."
    elif positive_count > 0 and negative_count > 0:
        mood = "mixed"
        mood_label = "호재/악재 혼재"
        one_line = f"{query} 관련 뉴스는 호재와 악재가 섞여 있습니다."
    else:
        mood = "neutral"
        mood_label = "중립"
        one_line = f"{query} 관련 뉴스는 뚜렷한 방향성이 아직 약합니다."

    all_themes = []
    positive_factors = []
    negative_factors = []

    for article in analyzed:
        all_themes.extend(article["themes"])
        positive_factors.extend(article["positiveKeywords"])
        negative_factors.extend(article["negativeKeywords"])

    key_themes = list(dict.fromkeys(all_themes))[:5]
    positive_factors = list(dict.fromkeys(positive_factors))[:5]
    negative_factors = list(dict.fromkeys(negative_factors))[:5]

    sorted_articles = sorted(
        analyzed,
        key=lambda x: x["importance"],
        reverse=True
    )

    if mood == "positive":
        takeaway = "긍정적 뉴스가 많지만 실제 공시나 실적 숫자로 이어지는지 확인해야 합니다."
    elif mood == "negative":
        takeaway = "악재성 뉴스가 많아 단기 변동성 확대 가능성을 주의해야 합니다."
    elif mood == "mixed":
        takeaway = "호재와 악재가 함께 있어 재료의 지속성과 실제 영향을 구분해야 합니다."
    else:
        takeaway = "아직 강한 재료는 부족해 보이며 추가 뉴스나 공시 확인이 필요합니다."

    return {
        "query": query,
        "generatedAt": datetime.now().isoformat(),
        "newsCount": len(articles),
        "mood": mood,
        "moodLabel": mood_label,
        "score": score,
        "oneLineSummary": one_line,
        "keyThemes": key_themes,
        "positiveFactors": positive_factors,
        "negativeFactors": negative_factors,
        "riskFlags": make_risk_flags(analyzed),
        "topNews": sorted_articles[:top_count],
        "investorTakeaway": takeaway,
        "caution": "뉴스 제목 기반 분석입니다. 기사 원문, 공시, 실적 확인이 필요하며 투자 추천이 아닙니다."
    }


@app.get("/")
def home():
    return {
        "message": "Stock News Insight API is running",
        "singleStockTest": "/v1/news/insight?query=삼성전자",
        "watchlistTest": "/v1/news/watchlist-insight?queries=삼성전자,SK하이닉스,에코프로"
    }


@app.get("/v1/news/insight")
def news_insight(
    query: str = Query(..., description="분석할 종목명. 예: 삼성전자"),
    limit: int = Query(default=10, ge=3, le=15),
    top: int = Query(default=5, ge=1, le=5)
):
    articles = get_google_news(query, limit)
    return build_insight(query, articles, top)


@app.get("/v1/news/watchlist-insight")
def watchlist_insight(
    queries: str = Query(..., description="쉼표로 구분한 종목명. 예: 삼성전자,SK하이닉스,에코프로"),
    limit: int = Query(default=8, ge=3, le=10)
):
    query_list = [q.strip() for q in queries.split(",") if q.strip()]
    query_list = query_list[:5]

    items = []

    for query in query_list:
        articles = get_google_news(query, limit)
        insight = build_insight(query, articles, 2)

        items.append({
            "query": insight["query"],
            "mood": insight["mood"],
            "moodLabel": insight["moodLabel"],
            "score": insight["score"],
            "oneLineSummary": insight["oneLineSummary"],
            "keyThemes": insight["keyThemes"],
            "riskFlags": insight["riskFlags"][:2],
            "topNews": insight["topNews"][:2],
            "investorTakeaway": insight["investorTakeaway"]
        })

    negative_items = [item["query"] for item in items if item["mood"] == "negative"]
    positive_items = [item["query"] for item in items if item["mood"] == "positive"]
    mixed_items = [item["query"] for item in items if item["mood"] == "mixed"]

    if negative_items:
        headline = "주의가 필요한 악재성 뉴스 종목이 있습니다: " + ", ".join(negative_items)
    elif mixed_items:
        headline = "호재와 악재가 섞인 종목이 있습니다: " + ", ".join(mixed_items)
    elif positive_items:
        headline = "긍정적 뉴스 흐름이 보이는 종목이 있습니다: " + ", ".join(positive_items)
    else:
        headline = "관심종목 뉴스 흐름은 전반적으로 중립에 가깝습니다."

    return {
        "generatedAt": datetime.now().isoformat(),
        "watchlistCount": len(items),
        "headline": headline,
        "items": items,
        "caution": "뉴스 제목 기반 분석입니다. 기사 원문, 공시, 실적 확인이 필요하며 투자 추천이 아닙니다."
    }
