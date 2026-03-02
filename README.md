# 🤖 AI 논문 데일리 다이제스트 — 완전 무료판

arXiv + Semantic Scholar 최신 AI 논문을 자동 수집,  
**Google Gemini API(무료)**로 한국어 + 영어 이중 요약 후 매일 오전 7시 Gmail 발송.  
**모든 비용 $0** — 서버도, 유료 API도 없습니다.

---

## 💰 비용 내역

| 항목 | 비용 | 무료 한도 |
|---|---|---|
| GitHub Actions | **$0** | 월 2,000분 (하루 ~2분 사용) |
| Google Gemini API | **$0** | 일 1,500회 (하루 10편 요약 = 10회) |
| arXiv API | **$0** | 무제한 |
| Semantic Scholar API | **$0** | 무제한 |
| Gmail SMTP | **$0** | 무제한 |

> ✅ **완전 무료** — 유료 API 키 불필요

---

## 🚀 설치 (5분)

### 1단계 — Gemini API 키 발급 (무료)

1. https://aistudio.google.com 접속 → Google 계정 로그인
2. 좌측 **"Get API key"** → **"Create API key"**
3. 생성된 키 복사 (`AIza...` 형식)

### 2단계 — Gmail 앱 비밀번호 발급

1. https://myaccount.google.com/security
2. **2단계 인증** 켜기 (필수)
3. **앱 비밀번호** → 이름: `AI Digest` → 생성
4. 16자리 비밀번호 복사

### 3단계 — GitHub 저장소 생성 & 업로드

```bash
git init
git add .
git commit -m "feat: AI paper daily digest (Gemini, free)"
# GitHub에서 새 저장소 생성 후:
git remote add origin https://github.com/YOUR_ID/ai-paper-digest.git
git push -u origin main
```

### 4단계 — GitHub Secrets 등록

저장소 → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

| Secret 이름 | 값 |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio에서 발급한 키 |
| `GMAIL_USER` | 발신 Gmail 주소 |
| `GMAIL_APP_PASSWORD` | Gmail 앱 비밀번호 (16자리) |
| `TO_EMAIL` | 수신 이메일 주소 |

### 5단계 — 테스트 실행

저장소 → **Actions** → **AI 논문 데일리 다이제스트** → **Run workflow**

5~10분 후 메일 수신 확인 ✅

---

## ⚙️ 커스터마이징

`fetch_and_send.py` 상단에서 수정:

```python
ARXIV_CATEGORIES = ["cs.AI", "cs.LG"]   # cs.CL, cs.CV, cs.RO 등 추가 가능
MAX_PAPERS       = 10                    # 하루 최대 편 수 (무료 한도 1,500회로 여유 충분)
```

**발송 시간 변경** (`.github/workflows/daily_digest.yml`):

```yaml
- cron: '0 21 * * *'   # 오전 6시 KST
- cron: '0 22 * * *'   # 오전 7시 KST  ← 현재 설정
- cron: '0 23 * * *'   # 오전 8시 KST
- cron: '0 12 * * *'   # 오후 9시 KST
```

---

## 📁 파일 구조

```
ai-paper-digest/
├── fetch_and_send.py              # 메인 스크립트
├── .github/
│   └── workflows/
│       └── daily_digest.yml       # GitHub Actions 스케줄
└── README.md
```
