"""올리브영 - 건강식품 카테고리 BEST 랭킹 크롤러 (프로토타입).

실행하면 오늘 날짜로 data/raw/올리브영_YYYY-MM-DD.csv 파일을 만든다.
"""

import csv
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

SITE = "올리브영"
CATEGORY = "건강식품"
URL = "https://www.oliveyoung.co.kr/store/display/getCategoryShop.do?dispCatNo=10000020001&gateCd=Drawer&"

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "data" / "raw"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out_path = OUT_DIR / f"{SITE}_{today}.csv"

    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=UA, locale="ko-KR", viewport={"width": 1400, "height": 1000})
        page = context.new_page()

        page.goto(URL, timeout=20000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        items = page.locator("div.ct-product#mRnkGoodsSec > div.item")
        count = items.count()
        print(f"발견된 상품 수: {count}")

        for i in range(count):
            item = items.nth(i)
            try:
                rank = item.locator("span.num").first.inner_text().strip()
                name = item.locator("span.prd-name").first.inner_text().strip()
                price_raw = item.locator("p.price span.price-2").first.inner_text()
                price = "".join(ch for ch in price_raw if ch.isdigit())
                brand = item.locator("button.btn_zzim").first.get_attribute("data-ref-goodsbrand") or ""
            except Exception as e:
                print("항목 파싱 실패:", e)
                continue

            if not name or not price:
                continue

            rows.append({
                "수집일": today,
                "사이트": SITE,
                "카테고리": CATEGORY,
                "순위": rank,
                "브랜드": brand,
                "상품명": name,
                "가격": price,
            })

        browser.close()

    if not rows:
        print("수집된 상품이 없습니다. 사이트 구조가 바뀌었을 수 있어요.")
        raise SystemExit(1)

    fieldnames = ["수집일", "사이트", "카테고리", "순위", "브랜드", "상품명", "가격"]
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
