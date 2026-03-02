#!/usr/bin/env python3
"""
AI Paper Daily Digest
─────────────────────
소스:  arXiv (cs.AI, cs.LG) + Semantic Scholar
요약:  한국어 + 영어 이중 요약 (Google Gemini API — 완전 무료)
발송:  Gmail SMTP
비용:  $0 완전 무료
"""

import os, json, time, smtplib, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ══════════════════════════════════════════════
#  설정 (GitHub Secrets에서 주입)
# ══════════════════════════════════════════════
GEMINI_API_KEY     = os.environ["GEMINI_API_KEY"]       # Google AI Studio (무료)
GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
TO_EMAIL           = os.environ["TO_EMAIL"]

ARXIV_CATEGORIES = ["cs.AI", "cs.LG"]
MAX_PAPERS       = 10

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"   # 무료 모델
)


# ══════════════════════════════════════════════
#  1. arXiv 수집
# ══════════════════════════════════════════════
def fetch_arxiv() -> list[dict]:
    papers, seen = [], set()
    for cat in ARXIV_CATEGORIES:
        url = (
            "http://export.arxiv.org/api/query?"
            f"search_query={urllib.parse.quote('cat:' + cat)}"
            "&sortBy=submittedDate&sortOrder=descending&max_results=40"
        )
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                root = ET.fromstring(r.read())
            ns = {"a": "http://www.w3.org/2005/Atom"}
            cutoff = (datetime.utcnow() - timedelta(days=2)).strftime("%Y%m%d")

            for entry in root.findall("a:entry", ns):
                pub = entry.find("a:published", ns).text[:10].replace("-", "")
                if pub < cutoff:
                    break
                pid = entry.find("a:id", ns).text.split("/abs/")[-1]
                if pid in seen:
                    continue
                seen.add(pid)
                papers.append({
                    "source":   "arXiv",
                    "category": cat,
                    "id":       pid,
                    "title":    entry.find("a:title", ns).text.strip().replace("\n", " "),
                    "abstract": entry.find("a:summary", ns).text.strip().replace("\n", " ")[:800],
                    "authors":  [a.find("a:name", ns).text for a in entry.findall("a:author", ns)][:4],
                    "url":      f"https://arxiv.org/abs/{pid}",
                    "date":     f"{pub[:4]}-{pub[4:6]}-{pub[6:]}",
                })
        except Exception as e:
            print(f"[arXiv/{cat}] 오류: {e}")
        time.sleep(1)
    return papers


# ══════════════════════════════════════════════
#  2. Semantic Scholar 수집 (무료, 무키)
# ══════════════════════════════════════════════
def fetch_semantic_scholar() -> list[dict]:
    papers, seen = [], set()
    queries = ["large language model 2025", "deep learning 2025"]
    for q in queries:
        url = (
            "https://api.semanticscholar.org/graph/v1/paper/search?"
            f"query={urllib.parse.quote(q)}"
            "&fields=title,abstract,authors,year,url&limit=8"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AI-Digest/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
            for p in data.get("data", []):
                if not p.get("abstract") or p["paperId"] in seen:
                    continue
                seen.add(p["paperId"])
                papers.append({
                    "source":   "Semantic Scholar",
                    "category": "AI",
                    "id":       p["paperId"],
                    "title":    p.get("title", ""),
                    "abstract": p.get("abstract", "")[:800],
                    "authors":  [a["name"] for a in p.get("authors", [])][:4],
                    "url":      p.get("url") or f"https://www.semanticscholar.org/paper/{p['paperId']}",
                    "date":     str(p.get("year", datetime.now().year)),
                })
        except Exception as e:
            print(f"[SemanticScholar] 오류: {e}")
        time.sleep(1)
    return papers[:5]


# ══════════════════════════════════════════════
#  3. Gemini API 이중 요약 (완전 무료)
#     gemini-2.0-flash: 일 1,500회 / 분 15회 무료
# ══════════════════════════════════════════════
def summarize(papers: list[dict]) -> list[dict]:
    results = []
    for i, p in enumerate(papers):
        print(f"  [{i+1}/{len(papers)}] {p['title'][:55]}...")

        prompt = f"""Summarize this AI paper in both Korean and English.

Title: {p['title']}
Abstract: {p['abstract']}

Reply ONLY with valid JSON (no markdown fences, no extra text):
{{
  "title_kr": "제목 한국어 번역",
  "summary_kr": "핵심 내용 3문장 (한국어)",
  "contribution_kr": "주요 기여 1-2문장 (한국어)",
  "summary_en": "3-sentence English summary",
  "contribution_en": "1-2 sentence key contribution (English)",
  "keywords": ["keyword1", "keyword2", "keyword3"]
}}"""

        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 800},
        }).encode()

        req = urllib.request.Request(
            GEMINI_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                resp = json.loads(r.read())
            raw = resp["candidates"][0]["content"]["parts"][0]["text"]
            raw = raw[raw.find("{"):raw.rfind("}")+1]
            summary = json.loads(raw)
        except Exception as e:
            print(f"    요약 실패: {e}")
            summary = {
                "title_kr": p["title"],
                "summary_kr": p["abstract"][:200] + "…",
                "contribution_kr": "요약 생성 실패",
                "summary_en": p["abstract"][:200] + "…",
                "contribution_en": "Summary generation failed",
                "keywords": [],
            }

        results.append({**p, **summary})
        time.sleep(4)   # 무료 티어: 분당 15회 제한 → 4초 간격으로 여유있게 유지

    return results


# ══════════════════════════════════════════════
#  4. HTML 이메일 빌드
# ══════════════════════════════════════════════
def build_html(papers: list[dict]) -> str:
    today_kr = datetime.now().strftime("%Y년 %m월 %d일")
    source_color = {"arXiv": "#1a73e8", "Semantic Scholar": "#0f9d58"}

    cards = ""
    for i, p in enumerate(papers, 1):
        color = source_color.get(p.get("source", ""), "#1a73e8")
        kw_html = "".join(
            f'<span style="background:#f1f3f4;color:#444;padding:3px 10px;'
            f'border-radius:12px;font-size:12px;margin:2px;">{kw}</span>'
            for kw in p.get("keywords", [])
        )
        cards += f"""
<div style="background:#fff;border-radius:14px;padding:26px 28px;margin-bottom:22px;
            box-shadow:0 2px 8px rgba(0,0,0,0.07);border-left:5px solid {color};">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
    <span style="background:{color};color:#fff;border-radius:50%;width:26px;height:26px;
                 display:inline-flex;align-items:center;justify-content:center;
                 font-size:13px;font-weight:700;">{i}</span>
    <span style="font-size:11px;color:#888;">{p.get('source','')} · {p.get('category','')} · {p.get('date','')}</span>
  </div>
  <h2 style="margin:0 0 4px;font-size:18px;color:#111;">{p.get('title_kr', p['title'])}</h2>
  <p style="margin:0 0 14px;font-size:12px;color:#999;font-style:italic;">{p['title']}</p>
  <table style="width:100%;border-collapse:collapse;margin-bottom:14px;">
    <tr>
      <td style="width:50%;padding:12px 14px;background:#f8f9ff;border-radius:8px 0 0 8px;
                 vertical-align:top;border:1px solid #e8eaf6;border-right:none;">
        <div style="font-size:11px;font-weight:700;color:{color};margin-bottom:6px;">🇰🇷 한국어 요약</div>
        <p style="margin:0 0 8px;font-size:13px;color:#333;line-height:1.7;">{p.get('summary_kr','')}</p>
        <div style="font-size:11px;font-weight:700;color:#555;margin-bottom:4px;">💡 주요 기여</div>
        <p style="margin:0;font-size:12px;color:#555;line-height:1.6;">{p.get('contribution_kr','')}</p>
      </td>
      <td style="width:50%;padding:12px 14px;background:#f9fff9;border-radius:0 8px 8px 0;
                 vertical-align:top;border:1px solid #e6f4ea;border-left:none;">
        <div style="font-size:11px;font-weight:700;color:#0f9d58;margin-bottom:6px;">🇺🇸 English Summary</div>
        <p style="margin:0 0 8px;font-size:13px;color:#333;line-height:1.7;">{p.get('summary_en','')}</p>
        <div style="font-size:11px;font-weight:700;color:#555;margin-bottom:4px;">💡 Key Contribution</div>
        <p style="margin:0;font-size:12px;color:#555;line-height:1.6;">{p.get('contribution_en','')}</p>
      </td>
    </tr>
  </table>
  <div style="margin-bottom:10px;">{kw_html}</div>
  <div style="font-size:12px;color:#888;">
    👥 {', '.join(p.get('authors', [])) or '저자 미상'}
    &nbsp;·&nbsp;
    <a href="{p['url']}" style="color:{color};text-decoration:none;">논문 원문 →</a>
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
    <h1 style="margin:0 0 6px;font-size:26px;">AI 논문 데일리 다이제스트</h1>
    <p style="margin:0;opacity:.85;font-size:14px;">
      {today_kr} &nbsp;·&nbsp; Top {len(papers)}편 &nbsp;·&nbsp; arXiv + Semantic Scholar
    </p>
  </div>
  {cards}
  <div style="text-align:center;padding:18px;font-size:12px;color:#aaa;line-height:1.8;">
    🔬 arXiv (cs.AI · cs.LG) &amp; Semantic Scholar<br>
    Gemini AI 자동 요약 · GitHub Actions 무료 자동화 · 매일 오전 7시 KST
  </div>
</div>
</body>
</html>"""


# ══════════════════════════════════════════════
#  5. Gmail 발송
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

    print("📡 arXiv 수집 중...")
    arxiv = fetch_arxiv()
    print(f"   → {len(arxiv)}편\n")

    print("📡 Semantic Scholar 수집 중...")
    scholar = fetch_semantic_scholar()
    print(f"   → {len(scholar)}편\n")

    all_papers = (arxiv + scholar)[:MAX_PAPERS]
    print(f"📚 총 {len(all_papers)}편 → Gemini 요약 시작\n")

    summarized = summarize(all_papers)

    print("\n📧 이메일 발송 중...")
    send_email(build_html(summarized), len(summarized))
    print("\n🎉 완료!")


if __name__ == "__main__":
    main()
