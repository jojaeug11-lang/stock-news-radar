from datetime import datetime
from urllib.parse import quote_plus

import feedparser
from fastapi import FastAPI, Query

app = FastAPI(title="Stock News Radar API", version="1.0.0")


def get_google_news(query: str, limit: int = 10):
    search_word = quote_plus(query)
    url = f"https://news.google.com/rss/search?q={search_word}&hl=ko&gl=KR&ceid=KR:ko"

    feed = feedparser.parse(url)

    articles = []

    for entry in feed.entries[:limit]:
        articles.append({
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "source": entry.get("source", {}).get("title") if entry.get("source") else "",
            "published": entry.get("published", "")
        })

    return articles


def simple_analyze(query: str, articles):
    positive_words = [
        "상승", "강세", "수주", "계약", "호재", "실적", "흑자",
        "성장", "급등", "기대", "개선", "돌파", "확대"
    ]

    negative_words = [
        "하락", "약세", "악재", "적자", "손실", "리콜", "소송",
        "우려", "급락", "부진", "감소", "논란", "압박"
    ]

    positive_count = 0
    negative_count = 0

    for article in articles:
        title = article["title"]

        if any(word in title for word in positive_words):
            positive_count += 1

        if any(word in title for word in negative_words):
            negative_count += 1

    if positive_count > negative_count:
        mood = "positive"
        mood_label = "호재 우세"
        summary = f"{query} 관련 뉴스는 호재성 표현이 더 많습니다."
    elif negative_count > positive_count:
        mood = "negative"
        mood_label = "악재 우세"
        summary = f"{query} 관련 뉴스는 악재성 표현이 더 많습니다."
    else:
        mood = "neutral"
        mood_label = "중립"
        summary = f"{query} 관련 뉴스는 아직 뚜렷한 호재/악재 방향이 약합니다."

    importance_score = min(100, (positive_count + negative_count) * 20)

    return {
        "mood": mood,
        "moodLabel": mood_label,
        "positiveCount": positive_count,
        "negativeCount": negative_count,
        "importanceScore": importance_score,
        "summary": summary
    }


@app.get("/")
def home():
    return {
        "message": "뉴스 레이더 서버가 켜졌습니다.",
        "singleStockTest": "/v1/news/radar?query=삼성전자",
        "watchlistTest": "/v1/news/watchlist?queries=삼성전자,SK하이닉스,에코프로"
    }


@app.get("/v1/news/radar")
def news_radar(
    query: str = Query(..., description="검색할 종목명. 예: 삼성전자"),
    limit: int = Query(default=10, ge=1, le=20)
):
    articles = get_google_news(query, limit)
    analysis = simple_analyze(query, articles)

    return {
        "query": query,
        "searchedAt": datetime.now().isoformat(),
        "articleCount": len(articles),
        "analysis": analysis,
        "topArticle": articles[0] if articles else None,
        "articles": articles,
        "caution": "뉴스 제목 기반의 간단 분석입니다. 투자 추천이 아닙니다."
    }


@app.get("/v1/news/watchlist")
def watchlist_news(
    queries: str = Query(..., description="쉼표로 구분한 종목명. 예: 삼성전자,SK하이닉스,에코프로"),
    limit: int = Query(default=5, ge=1, le=10)
):
    query_list = [q.strip() for q in queries.split(",") if q.strip()]

    results = []

    for query in query_list:
        articles = get_google_news(query, limit)
        analysis = simple_analyze(query, articles)

        results.append({
            "query": query,
            "articleCount": len(articles),
            "analysis": analysis,
            "topArticle": articles[0] if articles else None
        })

    negative_items = [
        item["query"]
        for item in results
        if item["analysis"]["mood"] == "negative"
    ]

    positive_items = [
        item["query"]
        for item in results
        if item["analysis"]["mood"] == "positive"
    ]

    if negative_items:
        headline = "악재성 뉴스가 더 많은 관심종목이 있습니다: " + ", ".join(negative_items)
    elif positive_items:
        headline = "호재성 뉴스가 더 많은 관심종목이 있습니다: " + ", ".join(positive_items)
    else:
        headline = "관심종목 뉴스 흐름은 전반적으로 중립에 가깝습니다."

    return {
        "searchedAt": datetime.now().isoformat(),
        "watchlistCount": len(results),
        "headline": headline,
        "items": results,
        "caution": "뉴스 제목 기반의 간단 분석입니다. 투자 추천이 아닙니다."
    }