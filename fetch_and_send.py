#!/usr/bin/env python3
"""
AI Paper Daily Digest
─────────────────────
소스:  arXiv (cs.AI, cs.LG) + Semantic Scholar
요약:  없음 — 원문 초록 그대로 발송 (빠르고 안정적)
발송:  Gmail SMTP
비용:  $0 완전 무료
예상 실행시간: ~30초
"""

import os, json, time, smtplib, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ══════════════════════════════════════════════
#  설정 (GitHub Secrets에서 주입)
# ══════════════════════════════════════════════
GMAIL_USER         = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
TO_EMAIL           = os.environ["TO_EMAIL"]

ARXIV_CATEGORIES = ["cs.AI", "cs.LG"]
MAX_PAPERS       = 10


# ══════════════════════════════════════════════
#  1. arXiv 수집
# ══════════════════════════════════════════════
def fetch_arxiv() -> list[dict]:
    papers, seen = [], set()
    for cat in ARXIV_CATEGORIES:
        url = (
            "https://export.arxiv.org/api/query?"
            f"search_query={urllib.parse.quote('cat:' + cat)}"
            "&sortBy=submittedDate&sortOrder=descending&max_results=20"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AI-Digest/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                root = ET.fromstring(r.read())
            ns = {"a": "http://www.w3.org/2005/Atom"}
            cutoff = (datetime.utcnow() - timedelta(days=7)).strftime("%Y%m%d")

            for entry in root.findall("a:entry", ns):
                pub = entry.find("a:published", ns).text[:10].replace("-", "")
                if pub < cutoff:
                    continue
                pid = entry.find("a:id", ns).text.split("/abs/")[-1]
                if pid in seen:
                    continue
                seen.add(pid)
                papers.append({
                    "source":   "arXiv",
                    "category": cat,
                    "id":       pid,
                    "title":    entry.find("a:title", ns).text.strip().replace("\n", " "),
                    "abstract": entry.find("a:summary", ns).text.strip().replace("\n", " "),
                    "authors":  [a.find("a:name", ns).text for a in entry.findall("a:author", ns)][:4],
                    "url":      f"https://arxiv.org/abs/{pid}",
                    "date":     f"{pub[:4]}-{pub[4:6]}-{pub[6:]}",
                })
        except Exception as e:
            print(f"[arXiv/{cat}] 오류: {e}")
        time.sleep(3)
    return papers


# ══════════════════════════════════════════════
#  2. Semantic Scholar 수집
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
        for attempt in range(3):
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
                        "abstract": p.get("abstract", ""),
                        "authors":  [a["name"] for a in p.get("authors", [])][:4],
                        "url":      p.get("url") or f"https://www.semanticscholar.org/paper/{p['paperId']}",
                        "date":     str(p.get("year", datetime.now().year)),
                    })
                break
            except Exception as e:
                wait = (attempt + 1) * 10
                print(f"[SemanticScholar] 오류 (시도 {attempt+1}/3): {e} → {wait}초 후 재시도")
                time.sleep(wait)
        time.sleep(3)
    return papers[:5]


# ══════════════════════════════════════════════
#  3. HTML 이메일 빌드 (원문 초록)
# ══════════════════════════════════════════════
def build_html(papers: list[dict]) -> str:
    today_kr = datetime.now().strftime("%Y년 %m월 %d일")
    source_color = {"arXiv": "#1a73e8", "Semantic Scholar": "#0f9d58"}

    cards = ""
    for i, p in enumerate(papers, 1):
        color = source_color.get(p.get("source", ""), "#1a73e8")
        abstract = p.get("abstract", "")

        cards += f"""
<div style="background:#fff;border-radius:14px;padding:26px 28px;margin-bottom:22px;
            box-shadow:0 2px 8px rgba(0,0,0,0.07);border-left:5px solid {color};">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
    <span style="background:{color};color:#fff;border-radius:50%;width:28px;height:28px;
                 display:inline-flex;align-items:center;justify-content:center;
                 font-size:13px;font-weight:700;flex-shrink:0;">{i}</span>
    <span style="font-size:12px;color:#888;">{p.get('source','')} &nbsp;·&nbsp; {p.get('category','')} &nbsp;·&nbsp; {p.get('date','')}</span>
  </div>
  <h2 style="margin:0 0 14px;font-size:18px;color:#111;line-height:1.4;">{p['title']}</h2>
  <div style="background:#f8f9fa;border-radius:10px;padding:16px;margin-bottom:14px;">
    <div style="font-size:11px;font-weight:700;color:#888;margin-bottom:8px;letter-spacing:0.5px;">ABSTRACT</div>
    <p style="margin:0;font-size:13px;color:#333;line-height:1.8;">{abstract}</p>
  </div>
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
      {today_kr} &nbsp;·&nbsp; Top {len(papers)}편 &nbsp;·&nbsp; arXiv + Semantic Scholar
    </p>
  </div>
  {cards}
  <div style="text-align:center;padding:18px;font-size:12px;color:#aaa;line-height:1.8;">
    🔬 arXiv (cs.AI · cs.LG) &amp; Semantic Scholar<br>
    GitHub Actions 무료 자동화 · 매일 오전 7시 KST
  </div>
</div>
</body>
</html>"""


# ══════════════════════════════════════════════
#  4. Gmail 발송
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
    print(f"📚 총 {len(all_papers)}편\n")

    print("📧 이메일 발송 중...")
    send_email(build_html(all_papers), len(all_papers))
    print("\n🎉 완료!")


if __name__ == "__main__":
    main()
