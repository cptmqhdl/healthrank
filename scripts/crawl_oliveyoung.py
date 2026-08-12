"""올리브영 - '판매랭킹 · 건강식품' 카테고리 베스트 크롤러.

실행하면 오늘 날짜로 data/raw/올리브영_YYYY-MM-DD.csv 파일을 만든다.
"""

import csv
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

SITE = "올리브영"
CATEGORY = "건강식품"
AJAX_URL = (
    "https://www.oliveyoung.co.kr/store/main/getBestList.do?"
    "dispCatNo=900000100100001&fltDispCatNo=10000020001&pageIdx=1&rowsPerPage=10"
    "&t_page=%EC%B9%B4%ED%85%8C%EA%B3%A0%EB%A6%AC%EA%B4%80"
    "&t_click=%EB%9E%AD%ED%82%B9BEST%EC%83%81%ED%92%88%EB%B8%8C%EB%9E%9C%EB%93%9C_%EC%9D%B8%EA%B8%B0%EC%83%81%ED%92%88%EB%8D%94%EB%B3%B4%EA%B8%B0"
)
TOP_N = 10
KST = timezone(timedelta(hours=9))

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "data" / "raw"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    collected_at = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    out_path = OUT_DIR / f"{SITE}_{today}.csv"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=UA, locale="ko-KR")
        page = context.new_page()

        # getBestList.do는 일반 페이지 이동으로 접근하면 전체 페이지 셸을 돌려주고,
        # 올리브영 사이트를 한 번 방문해 세션을 확보한 뒤 XHR로 호출해야 실제
        # "판매랭킹 · 건강식품" 목록(HTML 조각이 아니라 페이지 내부에 렌더링된 리스트)이
        # fltDispCatNo 필터가 적용된 상태로 내려온다.
        page.goto("https://www.oliveyoung.co.kr/store/main/main.do", timeout=20000, wait_until="domcontentloaded")
        page.wait_for_timeout(1000)

        raw_items = page.evaluate(
            """
            async (url) => {
              const res = await fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                credentials: 'include'
              });
              const html = await res.text();
              const doc = new DOMParser().parseFromString(html, 'text/html');
              return Array.from(doc.querySelectorAll('ul.cate_prd_list > li')).map(li => {
                const rankEl = li.querySelector('.thumb_flag.best');
                const brandEl = li.querySelector('.tx_brand');
                const nameEl = li.querySelector('.tx_name');
                const priceEl = li.querySelector('.prd_price .tx_cur .tx_num');
                const linkEl = li.querySelector('a.prd_thumb');
                const imgEl = li.querySelector('a.prd_thumb img');
                return {
                  rank: rankEl ? rankEl.textContent.trim() : null,
                  brand: brandEl ? brandEl.textContent.trim() : null,
                  name: nameEl ? nameEl.textContent.trim() : null,
                  price: priceEl ? priceEl.textContent.trim() : null,
                  link: linkEl ? linkEl.getAttribute('href') : null,
                  image: imgEl ? imgEl.getAttribute('src') : null,
                };
              });
            }
            """,
            AJAX_URL,
        )
        browser.close()

    print(f"발견된 상품 수: {len(raw_items)}")

    rows = []
    for raw in raw_items:
        if not (raw["rank"] and raw["name"] and raw["price"]):
            continue
        rank = int(raw["rank"])
        if rank > TOP_N:
            continue
        rows.append({
            "수집일": today,
            "수집시각": collected_at,
            "사이트": SITE,
            "카테고리": CATEGORY,
            "순위": rank,
            "브랜드": raw["brand"] or "",
            "상품명": raw["name"],
            "가격": raw["price"].replace(",", ""),
            "링크": raw["link"] or "",
            "이미지": raw["image"] or "",
        })

    if not rows:
        print("수집된 상품이 없습니다. 사이트 구조가 바뀌었을 수 있어요.")
        raise SystemExit(1)

    rows.sort(key=lambda r: r["순위"])

    fieldnames = ["수집일", "수집시각", "사이트", "카테고리", "순위", "브랜드", "상품명", "가격", "링크", "이미지"]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"저장 완료: {out_path} ({len(rows)}개 상품)")
    for r in rows[:10]:
        print(f"  {r['순위']:>2}위  {r['브랜드']:<10} {r['상품명'][:30]:<30} {r['가격']}원")


if __name__ == "__main__":
    main()
