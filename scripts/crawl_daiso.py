"""다이소몰 - '건강식품' 카테고리 페이지의 '건강식품 카테고리별 랭킹' 위젯 크롤러.

실행하면 오늘 날짜로 data/raw/다이소몰_YYYY-MM-DD.csv 파일을 만든다.
"""

import csv
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

SITE = "다이소몰"
CATEGORY = "건강식품"
URL = "https://www.daisomall.co.kr/ds/diy2/C246"
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
        context = browser.new_context(user_agent=UA, locale="ko-KR", viewport={"width": 1400, "height": 1000})
        page = context.new_page()

        page.goto(URL, timeout=40000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # "건강식품 카테고리별 랭킹" 위젯까지 스크롤해야 실제 렌더링된다.
        # 기존에는 Playwright의 scroll_into_view_if_needed(액션 전 요소가 "안정적으로
        # 멈춰있는지"까지 확인)를 썼는데, 위쪽 배너가 자동으로 움직이는 페이지라 요소
        # 위치가 계속 흔들려 30초 타임아웃이 CI에서 반복 발생했다(2026-08-15/16/18
        # 전부 동일한 Locator.scroll_into_view_if_needed 타임아웃으로 실패). 대신
        # 브라우저 네이티브 scrollIntoView를 evaluate로 직접 호출하면 "안정성" 대기 없이
        # 즉시 스크롤되어 이 문제를 피할 수 있다.
        widget = page.get_by_text("건강식품 카테고리별 랭킹", exact=True).first
        widget.wait_for(state="attached", timeout=30000)
        for attempt in range(3):
            try:
                widget.evaluate("el => el.scrollIntoView({block: 'center'})")
                break
            except Exception:
                if attempt == 2:
                    raise
                print(f"위젯 스크롤 {attempt + 1}차 시도 실패, 재시도합니다.")
                page.wait_for_timeout(3000)
        page.wait_for_timeout(2500)

        # 스와이프 캐러셀이라 카드 하나씩 순서대로 접근하면 화면이 움직여 타임아웃이 날 수
        # 있어, JS로 한 번에 전체 카드 데이터를 스냅샷 떠서 가져온다.
        raw_items = page.evaluate("""
            () => Array.from(document.querySelectorAll('div.nav-rank div.product-card')).map(card => {
                const numEl = card.querySelector('.rank .num');
                const nameEl = card.querySelector('.product-title');
                const priceEl = card.querySelector('.price-value .value');
                const linkEl = card.querySelector('a.prod-thumb__link');
                const imgEl = card.querySelector('.prod-thumb img');
                return {
                    rank: numEl ? numEl.textContent.trim() : null,
                    name: nameEl ? nameEl.textContent.trim() : null,
                    price: priceEl ? priceEl.textContent.trim() : null,
                    link: linkEl ? linkEl.getAttribute('href') : null,
                    // 스와이프 캐러셀은 swiper-lazy로 이미지를 지연 로딩해, 화면에
                    // 아직 노출되지 않은 카드는 src가 placeholder(noimage.png)이고
                    // 실제 주소는 data-src에 미리 들어있다. data-src를 우선 사용한다.
                    image: imgEl ? (imgEl.getAttribute('data-src') || imgEl.getAttribute('src')) : null,
                };
            })
        """)
        print(f"발견된 상품 수: {len(raw_items)}")

        rows = []
        for raw in raw_items:
            if not (raw["rank"] and raw["name"] and raw["price"]):
                continue
            rank = int(raw["rank"])
            if rank > TOP_N:
                continue
            href = raw["link"] or ""
            link = ("https://www.daisomall.co.kr" + href) if href.startswith("/") else href

            rows.append({
                "수집일": today,
                "수집시각": collected_at,
                "사이트": SITE,
                "카테고리": CATEGORY,
                "순위": rank,
                "브랜드": "",
                "상품명": raw["name"],
                "가격": raw["price"].replace(",", ""),
                "링크": link,
                "이미지": raw["image"] or "",
            })

        browser.close()

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
        print(f"  {r['순위']:>2}위  {r['상품명'][:35]:<35} {r['가격']}원")


if __name__ == "__main__":
    main()
