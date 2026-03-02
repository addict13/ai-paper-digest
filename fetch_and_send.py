#!/usr/bin/env python3
"""
AI Paper Daily Digest
─────────────────────
소스:      arXiv (카테고리 + 키워드) + Semantic Scholar (인용수 기준)
           + Hugging Face Papers (트렌딩 기준)
인기도:    Semantic Scholar 인용수 + Hugging Face 추천수
발송:      Gmail SMTP
비용:      $0 완전 무료
"""

import os, json, time, smtplib, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ══════════════════════════════════════════════
#  설정
# ══════════════════════════════════════════════
GEMINI_API_KEY     = os.environ["GEMINI_API_KEY"]
GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
TO_EMAIL           = os.environ["TO_EMAIL"]

ARXIV_CATEGORIES = ["cs.AI", "cs.LG", "cs.RO"]
ARXIV_KEYWORDS   = ["large language model", "robot learning", "reinforcement learning",
                    "foundation model", "transformer"]
MAX_PAPERS       = 10

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
)


# ══════════════════════════════════════════════
#  1. arXiv 수집 (카테고리 + 키워드, 최신순)
# ══════════════════════════════════════════════
def fetch_arxiv() -> list[dict]:
    papers, seen = [], set()
    cutoff = "20250101"  # 2025년 이후 논문만 수집

    for cat in ARXIV_CATEGORIES:
        for kw in ARXIV_KEYWORDS:
            # 2705 CffcB9ac C804Ccb4B97c C778Cf54B529 (AND, Acf5Bc31 D3ecD568)
            query = urllib.parse.quote(f"cat:{cat} AND all:{kw}")
            url = (
                "https://export.arxiv.org/api/query?"
                f"search_query={query}"
                "&sortBy=submittedDate&sortOrder=descending&max_results=5"
            )
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "AI-Digest/1.0"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    root = ET.fromstring(r.read())
                ns = {"a": "http://www.w3.org/2005/Atom"}

                for entry in root.findall("a:entry", ns):
                    pub = entry.find("a:published", ns).text[:10].replace("-", "")
                    if pub < cutoff:
                        continue
                    pid = entry.find("a:id", ns).text.split("/abs/")[-1]
                    if pid in seen:
                        continue
                    seen.add(pid)
                    papers.append({
                        "source":      "arXiv",
                        "category":    cat,
                        "keyword":     kw,
                        "id":          pid,
                        "title":       entry.find("a:title", ns).text.strip().replace("\n", " "),
                        "abstract":    entry.find("a:summary", ns).text.strip().replace("\n", " "),
                        "authors":     [a.find("a:name", ns).text for a in entry.findall("a:author", ns)][:4],
                        "url":         f"https://arxiv.org/abs/{pid}",
                        "date":        f"{pub[:4]}-{pub[4:6]}-{pub[6:]}",
                        "citations":   0,
                        "stars":       0,
                        "popularity":  0,
                    })
            except Exception as e:
                print(f"[arXiv/{cat}/{kw}] 오류: {e}")
            time.sleep(2)

    return papers


# ══════════════════════════════════════════════
#  2. Semantic Scholar — 인용수 기준 인기 논문
# ══════════════════════════════════════════════
def fetch_semantic_scholar() -> list[dict]:
    papers, seen = [], set()
    queries = ["artificial intelligence", "large language model", "robotics"]

    for q in queries:
        # citationCount 필드 추가, citationCount 내림차순 정렬
        url = (
            "https://api.semanticscholar.org/graph/v1/paper/search?"
            f"query={urllib.parse.quote(q)}"
            "&fields=title,abstract,authors,year,url,citationCount"
            "&year=2025-"
            "&limit=8"
        )
        try:  # 1회만 시도 — 실패 시 해당 쿼리 건너뜀
            req = urllib.request.Request(url, headers={"User-Agent": "AI-Digest/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())

            for p in data.get("data", []):
                if not p.get("abstract") or p["paperId"] in seen:
                    continue
                if (p.get("year") or 0) < 2025:  # 2025년 이후만
                    continue
                seen.add(p["paperId"])
                citations = p.get("citationCount") or 0
                papers.append({
                    "source":     "Semantic Scholar",
                    "category":   "AI",
                    "keyword":    q,
                    "id":         p["paperId"],
                    "title":      p.get("title", ""),
                    "abstract":   p.get("abstract", ""),
                    "authors":    [a["name"] for a in p.get("authors", [])][:4],
                    "url":        p.get("url") or f"https://www.semanticscholar.org/paper/{p['paperId']}",
                    "date":       str(p.get("year", datetime.now().year)),
                    "citations":  citations,
                    "stars":      0,
                    "popularity": citations,
                })
        except Exception as e:
            print(f"[SemanticScholar/{q}] 오류: {e} → 건너뜀")
        time.sleep(3)

    # 인용수 내림차순 정렬 후 상위 반환
    papers.sort(key=lambda x: x["citations"], reverse=True)
    return papers[:6]


# ══════════════════════════════════════════════
#  3. Hugging Face Papers — 트렌딩 논문 (안정적, 무료)
# ══════════════════════════════════════════════
def fetch_hf_papers() -> list[dict]:
    """Hugging Face Daily Papers — 커뮤니티 추천 기반 트렌딩 논문"""
    papers, seen = [], set()
    url = "https://huggingface.co/api/daily_papers?limit=10"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AI-Digest/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())

        for item in data:
            p = item.get("paper", {})
            pid = p.get("id", "")
            if not p.get("summary") or pid in seen:
                continue
            # 2025년 이후만
            pub = (p.get("publishedAt") or "")[:10].replace("-", "")
            if pub and pub < "20250101":
                continue
            seen.add(pid)
            upvotes = item.get("numComments", 0) + item.get("totalScore", 0)
            papers.append({
                "source":     "Hugging Face",
                "category":   "AI",
                "keyword":    "",
                "id":         pid,
                "title":      p.get("title", ""),
                "abstract":   p.get("summary", ""),
                "authors":    [a.get("name","") for a in p.get("authors", [])][:4],
                "url":        f"https://huggingface.co/papers/{pid}",
                "date":       (p.get("publishedAt") or "")[:10],
                "citations":  0,
                "stars":      upvotes,
                "popularity": upvotes,
            })
    except Exception as e:
        print(f"[HuggingFace] 오류: {e} → 건너뜀")

    papers.sort(key=lambda x: x["popularity"], reverse=True)
    return papers[:5]


# ══════════════════════════════════════════════
#  4. 인기도 점수로 최종 정렬
# ══════════════════════════════════════════════
def rank_papers(arxiv, scholar, pwc) -> list[dict]:
    """
    arXiv: 최신순 유지 (인기도 측정 어려움)
    Semantic Scholar + PwC: 인기도(인용수/스타수) 내림차순 병합
    최종: arXiv 최신 논문 + 인기 논문 혼합
    """
    popular = scholar + pwc
    popular.sort(key=lambda x: x["popularity"], reverse=True)

    # arXiv 최신 5편 + 인기 논문 상위 5편 혼합
    seen_titles = set()
    final = []
    for p in (arxiv[:5] + popular):
        if p["title"] in seen_titles:
            continue
        seen_titles.add(p["title"])
        final.append(p)
        if len(final) >= MAX_PAPERS:
            break

    return final


# ══════════════════════════════════════════════
#  5. Gemini로 초록 한글 번역
#     - 번역만 (요약 X) → 1회 호출로 빠르고 안정적
#     - 429 대비: 논문 간 20초 간격 + 최대 2회 재시도
# ══════════════════════════════════════════════
def translate_abstracts(papers: list[dict]) -> list[dict]:
    for i, p in enumerate(papers):
        print(f"  [{i+1}/{len(papers)}] 번역 중: {p['title'][:50]}...")
        prompt = (
            "다음 논문 초록을 자연스러운 한국어로 번역해줘. "
            "번역문만 출력하고 다른 말은 하지 마.\n\n"
            f"{p['abstract']}"
        )
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
        }).encode()
        req = urllib.request.Request(
            GEMINI_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        translated = None
        try:  # 1회만 시도 — 실패 시 원문 표시 (재시도 대기 없음)
            with urllib.request.urlopen(req, timeout=40) as r:
                resp = json.loads(r.read())
            translated = resp["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print(f"    번역 실패 (원문으로 대체): {e}")

        p["abstract_kr"] = translated  # None이면 원문 표시
        time.sleep(5)  # 논문 간 5초 대기 (분당 12회 이내 유지)

    return papers


# ══════════════════════════════════════════════
#  6. HTML 이메일 빌드
# ══════════════════════════════════════════════
def build_html(papers: list[dict]) -> str:
    today_kr = datetime.now().strftime("%Y년 %m월 %d일")
    source_color = {
        "arXiv":             "#1a73e8",
        "Semantic Scholar":  "#0f9d58",
        "Hugging Face":      "#ff9d00",
    }

    cards = ""
    for i, p in enumerate(papers, 1):
        color   = source_color.get(p.get("source", ""), "#1a73e8")
        citations = p.get("citations", 0)
        stars     = p.get("stars", 0)

        # 인기도 뱃지
        popularity_html = ""
        if citations > 0:
            popularity_html += (
                f'<span style="background:#fce8e6;color:#c5221f;font-size:11px;'
                f'padding:2px 8px;border-radius:10px;margin-left:4px;">'
                f'📚 인용 {citations:,}회</span>'
            )
        if stars > 0:
            popularity_html += (
                f'<span style="background:#fff3e0;color:#e65100;font-size:11px;'
                f'padding:2px 8px;border-radius:10px;margin-left:4px;">'
                f'⭐ GitHub {stars:,}</span>'
            )

        kw_badge = ""
        if p.get("keyword"):
            kw_badge = (
                f'<span style="background:#e8f0fe;color:#1a73e8;font-size:11px;'
                f'padding:2px 8px;border-radius:10px;margin-left:4px;">'
                f'🔑 {p["keyword"]}</span>'
            )

        cards += f"""
<div style="background:#fff;border-radius:14px;padding:26px 28px;margin-bottom:22px;
            box-shadow:0 2px 8px rgba(0,0,0,0.07);border-left:5px solid {color};">
  <div style="display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:12px;">
    <span style="background:{color};color:#fff;border-radius:50%;width:28px;height:28px;
                 display:inline-flex;align-items:center;justify-content:center;
                 font-size:13px;font-weight:700;flex-shrink:0;">{i}</span>
    <span style="font-size:12px;color:#888;">{p.get('source','')} &nbsp;·&nbsp; {p.get('category','')} &nbsp;·&nbsp; {p.get('date','')}</span>
    {kw_badge}
    {popularity_html}
  </div>
  <h2 style="margin:0 0 14px;font-size:18px;color:#111;line-height:1.4;">{p['title']}</h2>
  <div style="background:#f8f9fa;border-radius:10px;padding:16px;margin-bottom:10px;">
    <div style="font-size:11px;font-weight:700;color:#888;margin-bottom:8px;letter-spacing:0.5px;">🇰🇷 한국어 초록</div>
    <p style="margin:0;font-size:13px;color:#333;line-height:1.8;">{p.get('abstract_kr') or '(번역 실패 — 원문을 확인해주세요)'}</p>
  </div>
  <details style="margin-bottom:14px;">
    <summary style="font-size:11px;color:#aaa;cursor:pointer;">영문 원문 보기</summary>
    <div style="background:#f0f0f0;border-radius:8px;padding:12px;margin-top:8px;">
      <p style="margin:0;font-size:12px;color:#555;line-height:1.7;">{p.get('abstract','')}</p>
    </div>
  </details>
  <div style="font-size:12px;color:#888;">
    👥 {', '.join(p.get('authors', [])) or '저자 미상'}
    &nbsp;·&nbsp;
    <a href="{p['url']}" style="color:{color};text-decoration:none;font-weight:600;">논문 원문 보기 →</a>
  </div>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f4f8;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans KR',sans-serif;">
<div style="max-width:720px;margin:0 auto;padding:28px 16px;">
  <div style="background:linear-gradient(135deg,#1a73e8,#0d47a1);border-radius:18px;
              padding:36px 32px;text-align:center;margin-bottom:28px;color:#fff;">
    <div style="font-size:40px;margin-bottom:10px;">🤖</div>
    <h1 style="margin:0 0 6px;font-size:26px;font-weight:700;">AI 논문 데일리 다이제스트</h1>
    <p style="margin:0;opacity:.85;font-size:14px;">
      {today_kr} &nbsp;·&nbsp; Top {len(papers)}편 &nbsp;·&nbsp; AI · Robotics
    </p>
    <div style="margin-top:12px;font-size:12px;opacity:.75;">
      📚 인용수 · ⭐ GitHub 스타수 기반 인기도 반영
    </div>
  </div>
  {cards}
  <div style="text-align:center;padding:18px;font-size:12px;color:#aaa;line-height:1.8;">
    🔬 arXiv · Semantic Scholar · Hugging Face Papers<br>
    GitHub Actions 무료 자동화 · 매일 오전 7시 KST
  </div>
</div>
</body>
</html>"""


# ══════════════════════════════════════════════
#  6. Gmail 발송
# ══════════════════════════════════════════════
def send_email(html: str, count: int):
    today = datetime.now().strftime("%Y.%m.%d")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🤖 AI 논문 다이제스트 {today} — Top {count}편"
    msg["From"]    = GMAIL_USER
    msg["To"]      = TO_EMAIL
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        s.sendmail(GMAIL_USER, TO_EMAIL, msg.as_string())
    print(f"✅ 메일 발송 완료 → {TO_EMAIL}")


# ══════════════════════════════════════════════
#  메인
# ══════════════════════════════════════════════
def main():
    print(f"\n🚀 AI 논문 다이제스트 시작 · {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}\n")

    print("📡 [1/3] arXiv 수집 중 (최신순)...")
    arxiv = fetch_arxiv()
    print(f"   → {len(arxiv)}편\n")

    print("📡 [2/3] Semantic Scholar 수집 중 (인용수 기준)...")
    scholar = fetch_semantic_scholar()
    print(f"   → {len(scholar)}편\n")

    print("📡 [3/3] Hugging Face 트렌딩 논문 수집 중...")
    pwc = fetch_hf_papers()
    print(f"   → {len(pwc)}편\n")

    ranked = rank_papers(arxiv, scholar, pwc)
    print(f"📊 인기도 반영 후 최종 {len(ranked)}편\n")

    print("🌐 [4/4] Gemini로 초록 한글 번역 중...")
    ranked = translate_abstracts(ranked)
    print()

    print("📧 이메일 발송 중...")
    send_email(build_html(ranked), len(ranked))
    print("\n🎉 완료!")


if __name__ == "__main__":
    main()
