# Hot News 프로젝트 구조 가이드

## 전체 구조

```
hot-news/
├── app.py                  # Flask 서버 (API 엔드포인트, 캐시)
├── scrapers/
│   ├── community.py        # 커뮤니티 스크래퍼 (인벤, 루리웹, 디씨 등)
│   ├── news.py             # 뉴스 스크래퍼 (네이버, 네이트 등)
│   └── hotdeal.py          # 핫딜 스크래퍼 (뽐뿌, 클리앙)
├── templates/
│   └── index.html          # 프론트엔드 (HTML + JS, 단일 파일)
├── requirements.txt        # Python 패키지 목록
└── vercel.json             # Vercel 배포 설정
```

---

## 요청 흐름

```
브라우저 → index.html → fetch("/api/community/ruliweb")
                              ↓
                           app.py
                          캐시 확인
                        ↙         ↘
                  캐시 히트         캐시 미스
                  즉시 반환    scrapers/community.py 실행
                                  외부 사이트 스크래핑
                                  캐시 저장 후 반환
```

---

## app.py — 서버 & 캐시

### API 엔드포인트 3종

| 엔드포인트 | 예시 | 담당 스크래퍼 |
|---|---|---|
| `/api/community/<source>` | `/api/community/ruliweb` | `SCRAPERS` |
| `/api/news/<category>` | `/api/news/economy` | `NEWS_SCRAPERS` |
| `/api/hotdeal/<source>` | `/api/hotdeal/ppomppu` | `HOTDEAL_SCRAPERS` |

### 캐시 동작

- **CACHE_TTL = 3600초 (1시간)**: 서버 메모리에 결과 보관
- 캐시가 살아있으면 스크래핑 없이 즉시 반환
- 스크래핑 실패 시 이전 캐시 그대로 유지 (빈 결과 방지)
- **주의**: Vercel 서버리스는 인스턴스가 재시작되면 캐시 초기화됨

### CDN 캐시 헤더

```python
"Cache-Control": "public, s-maxage=3600, stale-while-revalidate=60"
```
Vercel 엣지 서버가 응답을 캐싱 → Cold Start 영향 완화

---

## scrapers/community.py — 커뮤니티

### 지원 사이트

| key | 사이트 | 특이사항 |
|---|---|---|
| `inven` | 인벤 오픈이슈 | 오늘의화제 top10 + 게시판 목록 |
| `ruliweb` | 루리웹 유머 베스트 | `bbs.ruliweb.com` (m. 에서 변경됨) |
| `dcinside` | 디씨 베스트 | 공지 번호 필터링 |
| `theqoo` | 더쿠 HOT | 고정 게시물 필터링 |
| `bobaedream` | 보배드림 베스트 | 정치 글 자동 필터링 |
| `todayhumor` | 오늘의유머 BoB | |
| `dogdrip` | 개드립 인기글 | Cloudflare 우회 (`cloudscraper`) |
| `ppomppu` | 뽐뿌 핫게시물 | hot.php + 자유게시판 보충 |
| `mlbpark` | MLB파크 불펜 | |

### 핵심 유틸리티

```python
fetch(url, headers, timeout=8)
# requests.Session 사용, 자동 재시도 (서버 오류 + 타임아웃)

fetch_cf(url, timeout=15)
# Cloudflare 차단 사이트용 (cloudscraper 라이브러리)

fetch_pages(urls, headers, timeout=8, use_cf=False)
# 여러 페이지를 ThreadPoolExecutor로 병렬 요청
# 순차 6~10초 → 병렬 2~3초
```

### 재시도 설정

```python
Retry(total=3, connect=2, read=2, backoff_factor=0.4,
      status_forcelist=[500, 502, 503, 504])
```
HTTP 오류뿐 아니라 연결 실패, 타임아웃도 최대 2회 재시도

---

## scrapers/news.py — 뉴스

### 지원 카테고리

| key | 출처 | 내용 |
|---|---|---|
| `ent` | 네이트 | 연예 뉴스 일간 랭킹 |
| `sports` | 네이트 | 스포츠 뉴스 일간 랭킹 |
| `society` | 네이버 | 사회 (오늘 기사 최신순) |
| `economy` | 네이버 | 경제 |
| `stocks` | 네이버 | 증권 |
| `realestate` | 네이버 | 부동산 |
| `world` | 네이버 | 세계 |
| `it` | 네이버 | IT/과학 |
| `game` | 루리웹 | 게임 뉴스 |
| `domestic` | 뉴스트래블 | 국내 여행 |
| `overseas` | 뉴스트래블 | 해외 여행 |

네이버 뉴스는 **오늘 기사만** 필터링 (`_parse_minutes_ago` 함수)

---

## scrapers/hotdeal.py — 핫딜

| key | 사이트 | 내용 |
|---|---|---|
| `ppomppu` | 뽐뿌 | 핫딜 게시판 |
| `clien` | 클리앙 | 알뜰구매 게시판 |

---

## 새 소스 추가하는 법

예: 커뮤니티에 `MLB파크2` 추가

**1. 스크래퍼 함수 작성** (`scrapers/community.py`)
```python
def get_새소스():
    items = []
    seen = set()
    soups = fetch_pages([
        f"https://example.com/best?page={page}"
        for page in range(1, 3)
    ])
    for soup in soups:
        if not soup:
            continue
        for a in soup.select("a.title"):
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if not title or title in seen:
                continue
            seen.add(title)
            items.append({"rank": len(items)+1, "title": title, "url": href})
        if len(items) >= TARGET:
            break
    return items[:TARGET]
```

**2. SCRAPERS dict에 등록**
```python
SCRAPERS = {
    ...
    "새소스": get_새소스,   # ← 추가
}
```

**3. index.html에 탭/버튼 추가**
```html
<button data-source="새소스">새소스</button>
```

API는 자동으로 `/api/community/새소스` 로 열림

---

## 로컬 실행

```bash
pip install -r requirements.txt
python app.py
# http://localhost:5000
```

## 배포 (Vercel)

```bash
vercel --prod
```

`vercel.json`이 비어있어 기본 설정으로 Python WSGI 앱으로 인식됨
