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
@app.get("/v1/news/watchlist-summary")
def get_watchlist_gpt_summary(
    queries: str = Query(..., description="쉼표로 구분한 관심종목입니다. 예: 삼성전자,SK하이닉스,에코프로"),
    limit: int = Query(default=5, ge=3, le=8)
):
    query_list = [q.strip() for q in queries.split(",") if q.strip()]
    query_list = query_list[:10]

    if not query_list:
        return {
            "queries": [],
            "answer": "분석할 관심종목이 없습니다."
        }

    items = []

    positive_items = []
    negative_items = []
    neutral_items = []
    mixed_items = []

    for query in query_list:
        articles = get_google_news(query, limit)
        result = analyze_news(query, articles)

        mood = result["mood"]

        if mood == "호재 우세":
            positive_items.append(query)
        elif mood == "악재 우세":
            negative_items.append(query)
        elif mood == "호재/악재 혼재":
            mixed_items.append(query)
        else:
            neutral_items.append(query)

        key_themes = ", ".join(result["keyThemes"]) if result["keyThemes"] else "뚜렷한 핵심 테마 없음"
        positive_factors = ", ".join(result["positiveFactors"]) if result["positiveFactors"] else "뚜렷한 긍정 키워드 없음"
        negative_factors = ", ".join(result["negativeFactors"]) if result["negativeFactors"] else "뚜렷한 부정 키워드 없음"

        top_news_lines = []

        for index, news in enumerate(result["topNews"][:2], start=1):
            top_news_lines.append(
                f"{index}. {news['title']}\n"
                f"   - 출처: {news['source']}\n"
                f"   - 판단: {news['sentiment']}\n"
                f"   - 의미: {news['whyItMatters']}"
            )

        if not top_news_lines:
            top_news_lines.append("주요 뉴스를 찾지 못했습니다.")

        item_text = f"""
[{query}]
- 분위기: {result["mood"]}
- 요약: {result["summary"]}
- 핵심 테마: {key_themes}
- 긍정 요인: {positive_factors}
- 부정/위험 요인: {negative_factors}
- 주요 뉴스:
{chr(10).join(top_news_lines)}
""".strip()

        items.append(item_text)

    if negative_items:
        headline = "주의가 필요한 악재성 뉴스 종목이 있습니다: " + ", ".join(negative_items)
    elif mixed_items:
        headline = "호재와 악재가 섞인 종목이 있습니다: " + ", ".join(mixed_items)
    elif positive_items:
        headline = "긍정적 뉴스 흐름이 보이는 종목이 있습니다: " + ", ".join(positive_items)
    else:
        headline = "관심종목 뉴스 흐름은 전반적으로 중립에 가깝습니다."

    radar_summary = f"""
[관심종목 뉴스 레이더]

1. 전체 요약
- 분석 종목 수: {len(query_list)}개
- {headline}

2. 호재 우세 종목
- {", ".join(positive_items) if positive_items else "없음"}

3. 악재 우세 종목
- {", ".join(negative_items) if negative_items else "없음"}

4. 호재/악재 혼재 종목
- {", ".join(mixed_items) if mixed_items else "없음"}

5. 중립 종목
- {", ".join(neutral_items) if neutral_items else "없음"}

6. 종목별 상세
{chr(10).join(items)}

7. 오늘 확인할 점
- 악재 우세 종목은 기사 원문과 공시 여부를 먼저 확인하세요.
- 호재 우세 종목은 이미 주가에 반영된 재료인지 확인하세요.
- 뉴스 제목 기반 분석이므로 기사 원문, 공시, 실적 숫자를 함께 확인해야 합니다.
- 이 내용은 투자 참고용이며 매수·매도 추천이 아닙니다.
""".strip()

    return {
        "queries": query_list,
        "generatedAt": datetime.now().isoformat(),
        "answer": radar_summary
    }
@app.get("/v1/news/theme-summary")
def get_theme_gpt_summary(
    themes: str = Query(..., description="쉼표로 구분한 테마입니다. 예: 반도체,2차전지,원전,로봇,바이오"),
    limit: int = Query(default=5, ge=3, le=8)
):
    theme_list = [theme.strip() for theme in themes.split(",") if theme.strip()]
    theme_list = theme_list[:10]

    if not theme_list:
        return {
            "themes": [],
            "answer": "분석할 테마가 없습니다."
        }

    items = []

    positive_themes = []
    negative_themes = []
    mixed_themes = []
    neutral_themes = []

    scored_themes = []

    for theme in theme_list:
        search_query = f"{theme} 주식 관련주"
        articles = get_google_news(search_query, limit)
        result = analyze_news(theme, articles)

        mood = result["mood"]
        positive_count = result["positiveCount"]
        negative_count = result["negativeCount"]

        theme_score = (positive_count - negative_count) * 10
        theme_score += len(result["keyThemes"]) * 3

        scored_themes.append({
            "theme": theme,
            "score": theme_score,
            "mood": mood
        })

        if mood == "호재 우세":
            positive_themes.append(theme)
        elif mood == "악재 우세":
            negative_themes.append(theme)
        elif mood == "호재/악재 혼재":
            mixed_themes.append(theme)
        else:
            neutral_themes.append(theme)

        key_themes = ", ".join(result["keyThemes"]) if result["keyThemes"] else "뚜렷한 세부 테마 없음"
        positive_factors = ", ".join(result["positiveFactors"]) if result["positiveFactors"] else "뚜렷한 긍정 키워드 없음"
        negative_factors = ", ".join(result["negativeFactors"]) if result["negativeFactors"] else "뚜렷한 부정 키워드 없음"

        top_news_lines = []

        for index, news in enumerate(result["topNews"][:2], start=1):
            top_news_lines.append(
                f"{index}. {news['title']}\n"
                f"   - 출처: {news['source']}\n"
                f"   - 판단: {news['sentiment']}\n"
                f"   - 의미: {news['whyItMatters']}"
            )

        if not top_news_lines:
            top_news_lines.append("주요 뉴스를 찾지 못했습니다.")

        item_text = f"""
[{theme}]
- 분위기: {result["mood"]}
- 테마 점수: {theme_score}
- 요약: {result["summary"]}
- 세부 테마: {key_themes}
- 긍정 요인: {positive_factors}
- 부정/위험 요인: {negative_factors}
- 주요 뉴스:
{chr(10).join(top_news_lines)}
""".strip()

        items.append(item_text)

    sorted_scores = sorted(scored_themes, key=lambda x: x["score"], reverse=True)

    strongest_theme = sorted_scores[0]["theme"] if sorted_scores else "없음"
    weakest_theme = sorted_scores[-1]["theme"] if sorted_scores else "없음"

    if positive_themes:
        headline = "뉴스 흐름이 강한 테마가 있습니다: " + ", ".join(positive_themes)
    elif mixed_themes:
        headline = "호재와 악재가 섞인 테마가 있습니다: " + ", ".join(mixed_themes)
    elif negative_themes:
        headline = "주의가 필요한 테마가 있습니다: " + ", ".join(negative_themes)
    else:
        headline = "테마 뉴스 흐름은 전반적으로 중립에 가깝습니다."

    answer = f"""
[테마 뉴스 레이더]

1. 전체 요약
- 분석 테마 수: {len(theme_list)}개
- {headline}
- 가장 강한 테마 후보: {strongest_theme}
- 가장 약한 테마 후보: {weakest_theme}

2. 호재 우세 테마
- {", ".join(positive_themes) if positive_themes else "없음"}

3. 악재 우세 테마
- {", ".join(negative_themes) if negative_themes else "없음"}

4. 호재/악재 혼재 테마
- {", ".join(mixed_themes) if mixed_themes else "없음"}

5. 중립 테마
- {", ".join(neutral_themes) if neutral_themes else "없음"}

6. 테마별 상세
{chr(10).join(items)}

7. 오늘 확인할 점
- 강한 테마는 이미 주가에 반영된 재료인지 확인하세요.
- 약한 테마나 악재 우세 테마는 기사 원문과 공시 여부를 먼저 확인하세요.
- 테마 뉴스는 관련주 전체에 영향을 줄 수 있지만, 종목별 실적과 수급은 따로 확인해야 합니다.
- 뉴스 제목 기반 분석이며 투자 추천이 아닙니다.
""".strip()

    return {
        "themes": theme_list,
        "generatedAt": datetime.now().isoformat(),
        "strongestTheme": strongest_theme,
        "weakestTheme": weakest_theme,
        "answer": answer
    }
import json
import os
from datetime import date

SNAPSHOT_FILE = "news_snapshots.json"


def load_snapshots():
    if not os.path.exists(SNAPSHOT_FILE):
        return []

    try:
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return []


def save_snapshots(snapshots):
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as file:
        json.dump(snapshots, file, ensure_ascii=False, indent=2)


def mood_to_score(mood: str):
    if mood == "호재 우세":
        return 2
    if mood == "호재/악재 혼재":
        return 1
    if mood == "중립":
        return 0
    if mood == "악재 우세":
        return -2
    return 0


def make_snapshot_for_queries(query_list, limit):
    items = []

    for query in query_list:
        articles = get_google_news(query, limit)
        result = analyze_news(query, articles)

        items.append({
            "query": query,
            "mood": result["mood"],
            "score": mood_to_score(result["mood"]),
            "summary": result["summary"],
            "positiveCount": result["positiveCount"],
            "negativeCount": result["negativeCount"],
            "keyThemes": result["keyThemes"],
            "positiveFactors": result["positiveFactors"],
            "negativeFactors": result["negativeFactors"],
            "topNewsTitles": [news["title"] for news in result["topNews"][:3]]
        })

    return items


@app.get("/v1/news/save-snapshot")
def save_news_snapshot(
    queries: str = Query(..., description="쉼표로 구분한 관심종목입니다. 예: 삼성전자,SK하이닉스,에코프로"),
    limit: int = Query(default=5, ge=3, le=8)
):
    query_list = [q.strip() for q in queries.split(",") if q.strip()]
    query_list = query_list[:10]

    today_text = date.today().isoformat()

    snapshot = {
        "date": today_text,
        "savedAt": datetime.now().isoformat(),
        "queries": query_list,
        "items": make_snapshot_for_queries(query_list, limit)
    }

    snapshots = load_snapshots()
    snapshots.append(snapshot)

    # 너무 커지는 것을 막기 위해 최근 30개만 보관
    snapshots = snapshots[-30:]

    save_snapshots(snapshots)

    answer = f"""
[뉴스 스냅샷 저장 완료]

- 저장일: {today_text}
- 저장 종목 수: {len(query_list)}개
- 저장 종목: {", ".join(query_list)}

이제 다음 날 같은 관심종목으로 비교하면 어제 대비 오늘 뉴스 분위기 변화를 볼 수 있습니다.
""".strip()

    return {
        "date": today_text,
        "queries": query_list,
        "answer": answer
    }


@app.get("/v1/news/compare-snapshot")
def compare_news_snapshot(
    queries: str = Query(..., description="쉼표로 구분한 관심종목입니다. 예: 삼성전자,SK하이닉스,에코프로"),
    limit: int = Query(default=5, ge=3, le=8),
    saveCurrent: bool = Query(default=True, description="비교 후 오늘 스냅샷을 저장할지 여부입니다.")
):
    query_list = [q.strip() for q in queries.split(",") if q.strip()]
    query_list = query_list[:10]

    today_text = date.today().isoformat()

    snapshots = load_snapshots()

    previous_snapshot = None

    # 오늘이 아닌 가장 최근 스냅샷 찾기
    for snapshot in reversed(snapshots):
        if snapshot.get("date") != today_text:
            previous_snapshot = snapshot
            break

    current_items = make_snapshot_for_queries(query_list, limit)

    if previous_snapshot is None:
        if saveCurrent:
            snapshots.append({
                "date": today_text,
                "savedAt": datetime.now().isoformat(),
                "queries": query_list,
                "items": current_items
            })
            snapshots = snapshots[-30:]
            save_snapshots(snapshots)

        answer = f"""
[어제와 오늘 뉴스 비교]

아직 비교할 이전 스냅샷이 없습니다.

오늘 관심종목 뉴스 상태는 저장해두었습니다.
내일 다시 비교하면 오늘 저장값과 내일 뉴스 흐름을 비교할 수 있습니다.

분석 종목:
- {", ".join(query_list)}
""".strip()

        return {
            "hasPreviousSnapshot": False,
            "answer": answer
        }

    previous_items = previous_snapshot.get("items", [])
    previous_map = {item["query"]: item for item in previous_items}

    improved = []
    worsened = []
    unchanged = []
    details = []

    for current in current_items:
        query = current["query"]
        previous = previous_map.get(query)

        if not previous:
            details.append(f"[{query}]\n- 이전 저장값 없음\n- 오늘 분위기: {current['mood']}")
            continue

        diff = current["score"] - previous["score"]

        if diff > 0:
            change_label = "개선"
            improved.append(query)
        elif diff < 0:
            change_label = "악화"
            worsened.append(query)
        else:
            change_label = "비슷함"
            unchanged.append(query)

        new_themes = [
            theme for theme in current["keyThemes"]
            if theme not in previous.get("keyThemes", [])
        ]

        new_negative = [
            word for word in current["negativeFactors"]
            if word not in previous.get("negativeFactors", [])
        ]

        detail = f"""
[{query}]
- 이전 분위기: {previous["mood"]}
- 오늘 분위기: {current["mood"]}
- 변화 판단: {change_label}
- 이전 요약: {previous["summary"]}
- 오늘 요약: {current["summary"]}
- 새로 보이는 테마: {", ".join(new_themes) if new_themes else "특별히 새 테마 없음"}
- 새 부정 키워드: {", ".join(new_negative) if new_negative else "특별히 새 부정 키워드 없음"}
""".strip()

        details.append(detail)

    if worsened:
        headline = "뉴스 분위기가 나빠진 종목이 있습니다: " + ", ".join(worsened)
    elif improved:
        headline = "뉴스 분위기가 좋아진 종목이 있습니다: " + ", ".join(improved)
    else:
        headline = "관심종목 뉴스 분위기는 이전 저장값과 큰 차이가 없습니다."

    answer = f"""
[어제와 오늘 뉴스 변화 비교]

1. 전체 요약
- 비교 기준일: {previous_snapshot.get("date")}
- 오늘 날짜: {today_text}
- {headline}

2. 분위기 개선 종목
- {", ".join(improved) if improved else "없음"}

3. 분위기 악화 종목
- {", ".join(worsened) if worsened else "없음"}

4. 큰 변화 없는 종목
- {", ".join(unchanged) if unchanged else "없음"}

5. 종목별 변화
{chr(10).join(details)}

6. 확인할 점
- 악화 종목은 기사 원문, 공시, 실적 이슈를 우선 확인하세요.
- 개선 종목은 이미 주가에 반영된 재료인지 확인하세요.
- 이 비교는 뉴스 제목 기반 분석이며 투자 추천이 아닙니다.
""".strip()

    if saveCurrent:
        snapshots.append({
            "date": today_text,
            "savedAt": datetime.now().isoformat(),
            "queries": query_list,
            "items": current_items
        })
        snapshots = snapshots[-30:]
        save_snapshots(snapshots)

    return {
        "hasPreviousSnapshot": True,
        "previousDate": previous_snapshot.get("date"),
        "currentDate": today_text,
        "improved": improved,
        "worsened": worsened,
        "unchanged": unchanged,
        "answer": answer
    }
