import requests
import re
from bs4 import BeautifulSoup

PC_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


def fetch(url, headers=None, timeout=10):
    try:
        h = headers or PC_HEADERS
        r = requests.get(url, headers=h, timeout=timeout)
        r.raise_for_status()
        return BeautifulSoup(r.content, "lxml")
    except Exception as e:
        print(f"[fetch error] {url}: {e}")
        return None


def get_ppomppu():
    """뽐뿌 핫딜"""
    soup = fetch(
        "https://ppomppu.co.kr/zboard/zboard.php?id=ppomppu",
        headers={**MOBILE_HEADERS, "Referer": "https://ppomppu.co.kr/"},
    )
    if not soup:
        return []

    items = []
    seen = set()
    rank = 1

    for tr in soup.select("tr.baseList"):
        a = tr.find("a", href=lambda h: h and "view.php" in h and "id=ppomppu" in h)
        title_el = tr.select_one("td.baseList-space.title")
        if not a or not title_el:
            continue

        title = title_el.get_text(strip=True)
        # 끝 카테고리 [의류/잡화] 제거
        title = re.sub(r'\[[^\]]+/[^\]]+\]\s*$', '', title).strip()
        # 끝 단독 카테고리 [기타] 등 제거
        title = re.sub(r'\[[^\]]{1,10}\]\s*$', '', title).strip()
        # 끝 숫자(댓글 수) 제거
        title = re.sub(r'\d+$', '', title).strip()

        if not title or len(title) < 5 or title in seen:
            continue

        href = "https://ppomppu.co.kr/zboard/" + a.get("href", "").split("&&")[0]

        seen.add(title)
        items.append({"rank": rank, "title": title, "url": href})
        rank += 1
        if rank > 50:
            break

    return items[:50]


def get_clien_jirum():
    """클리앙 알뜰구매"""
    soup = fetch(
        "https://www.clien.net/service/board/jirum",
        headers={**PC_HEADERS, "Referer": "https://www.clien.net/"},
    )
    if not soup:
        return []

    items = []
    seen = set()
    rank = 1

    for div in soup.select("div.list_item"):
        # 공지·홍보·광고 제외
        cls = div.get("class", [])
        if "notice" in cls or "hongbo" in cls:
            continue

        a = div.find("a", href=lambda h: h and "/service/board/jirum/" in h)
        if not a:
            continue

        title_el = div.select_one(".subject_fixed")
        if not title_el:
            title_el = div.select_one(".list_subject")
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        # 끝 숫자(댓글 수) 제거
        title = re.sub(r'\d+$', '', title).strip()

        if not title or len(title) < 5 or title in seen:
            continue

        href = a.get("href", "").split("?")[0]
        if not href.startswith("http"):
            href = "https://www.clien.net" + href

        seen.add(title)
        items.append({"rank": rank, "title": title, "url": href})
        rank += 1
        if rank > 50:
            break

    return items[:50]


HOTDEAL_SCRAPERS = {
    "ppomppu": get_ppomppu,
    "clien": get_clien_jirum,
}
