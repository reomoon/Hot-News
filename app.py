from flask import Flask, jsonify, render_template, make_response, request
from scrapers.community import SCRAPERS
from scrapers.news import NEWS_SCRAPERS
from scrapers.hotdeal import HOTDEAL_SCRAPERS
import threading
import time
import os
import sqlite3

app = Flask(__name__)

# ===== 댓글 DB =====
_DATABASE_URL = os.environ.get('DATABASE_URL', '')
if _DATABASE_URL.startswith('postgres://'):
    _DATABASE_URL = _DATABASE_URL.replace('postgres://', 'postgresql://', 1)
_USE_PG = bool(_DATABASE_URL)

def _get_conn():
    if _USE_PG:
        import psycopg2
        return psycopg2.connect(_DATABASE_URL)
    conn = sqlite3.connect(os.path.join(os.path.dirname(__file__), 'comments.db'))
    conn.row_factory = sqlite3.Row
    return conn

def _init_db():
    conn = _get_conn()
    cur = conn.cursor()
    if _USE_PG:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id SERIAL PRIMARY KEY,
                url TEXT NOT NULL,
                nickname VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_comments_url ON comments(url)")
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                nickname TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_comments_url ON comments(url)")
    conn.commit()
    cur.close()
    conn.close()

_init_db()

# 캐시: 주기적으로 갱신
_cache = {}
_cache_lock = threading.Lock()
CACHE_TTL = 3600  # 10분 (서버 인스턴스 메모리 캐시)
CDN_TTL = 3600    # 10분 (Vercel CDN 엣지 캐시 - Cold Start 우회)


def get_cached(key, scraper_fn):
    now = time.time()
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (now - entry["ts"]) < CACHE_TTL:
            return entry["data"]
    try:
        data = scraper_fn()
    except Exception as e:
        print(f"[scraper error] {key}: {e}")
        data = None
    with _cache_lock:
        if data:
            _cache[key] = {"data": data, "ts": time.time()}
        elif entry:
            return entry["data"]  # 실패 시 이전 캐시 유지
        else:
            return []
    return data


def cached_response(data):
    """CDN 엣지 캐싱 헤더 포함 응답 - Cold Start 문제 해결"""
    resp = make_response(jsonify(data))
    resp.headers["Cache-Control"] = (
        f"public, s-maxage={CDN_TTL}, stale-while-revalidate=60"
    )
    return resp


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/community/<source>")
def api_community(source):
    if source not in SCRAPERS:
        return jsonify({"error": "unknown source"}), 404
    data = get_cached(f"community_{source}", SCRAPERS[source])
    return cached_response({"source": source, "items": data})


@app.route("/api/news/<category>")
def api_news(category):
    if category not in NEWS_SCRAPERS:
        return jsonify({"error": "unknown category"}), 404
    data = get_cached(f"news_{category}", NEWS_SCRAPERS[category])
    return cached_response({"category": category, "items": data})


@app.route("/api/hotdeal/<source>")
def api_hotdeal(source):
    if source not in HOTDEAL_SCRAPERS:
        return jsonify({"error": "unknown source"}), 404
    data = get_cached(f"hotdeal_{source}", HOTDEAL_SCRAPERS[source])
    return cached_response({"source": source, "items": data})

@app.route("/api/comments/counts", methods=["POST"])
def api_comment_counts():
    urls = (request.get_json(silent=True) or {}).get('urls', [])
    if not urls or len(urls) > 100:
        return jsonify({}), 400
    ph = '%s' if _USE_PG else '?'
    placeholders = ','.join([ph] * len(urls))
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT url, COUNT(*) FROM comments WHERE url IN ({placeholders}) GROUP BY url", urls)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify({r[0]: r[1] for r in rows})


@app.route("/api/comments")
def api_get_comments():
    url = request.args.get('url', '').strip()
    if not url:
        return jsonify({"error": "url required"}), 400
    ph = '%s' if _USE_PG else '?'
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT nickname, content, created_at FROM comments WHERE url={ph} ORDER BY created_at ASC", (url,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    comments = [{"nickname": r[0], "content": r[1], "created_at": str(r[2])[:16]} for r in rows]
    return jsonify({"comments": comments, "count": len(comments)})


@app.route("/api/comments", methods=["POST"])
def api_post_comment():
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').strip()
    nickname = data.get('nickname', '').strip()[:20]
    content = data.get('content', '').strip()[:300]
    if not url or not nickname or not content:
        return jsonify({"error": "url, nickname, content required"}), 400
    ph = '%s' if _USE_PG else '?'
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(f"INSERT INTO comments (url, nickname, content) VALUES ({ph},{ph},{ph})", (url, nickname, content))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True})


# 로컬 호스트 테스트 포트(ex. http://localhost:5000/)
if __name__ == "__main__":
    app.run(debug=True, port=5000)
