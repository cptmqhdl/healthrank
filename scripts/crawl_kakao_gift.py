"""카카오톡 선물하기 - 건강식품·영양제 랭킹 크롤러 (프로토타입 1호).

실행하면 오늘 날짜로 data/raw/카카오선물하기_YYYY-MM-DD.csv 파일을 만든다.
"""

import csv
import re
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

SITE = "카카오선물하기"
CATEGORY = "건강식품·영양제"
URL = "https://gift.kakao.com/ranking/category/8"

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "data" / "raw"


RANK_RE = re.compile(r"^(\d+)\s*\n위", re.MULTILINE)
BRAND_RE = re.compile(r"브랜드명\s*:\s*([^\n,]+)")
NAME_RE = re.compile(r"상품명\s*:\s*\n([^\n]+)")
PRICE_RE = re.compile(r"판매가\s*:\s*\n([\d,]+)\s*원")


def parse_item(text: str):
    """상품 카드 하나의 inner_text에서 순위/브랜드/상품명/가격을 뽑아낸다."""
    rank_m = RANK_RE.search(text)
    brand_m = BRAND_RE.search(text)
    name_m = NAME_RE.search(text)
    price_m = PRICE_RE.search(text)

    if not (brand_m and name_m and price_m):
        return None

    return {
        "순위": int(rank_m.group(1)) if rank_m else None,
        "브랜드": brand_m.group(1).strip(),
        "상품명": name_m.group(1).strip(),
        "가격": price_m.group(1).replace(",", ""),
        "광고여부": "Y" if "광고" in text.split("\n")[:3] else "N",
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out_path = OUT_DIR / f"{SITE}_{today}.csv"

    rows = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=UA, locale="ko-KR")
        page = context.new_page()

        page.goto(URL, timeout=20000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        cards = page.locator("div.unit_prd")
        count = cards.count()
        print(f"발견된 상품 카드 수: {count}")

        rank = 0
        for i in range(count):
            card = cards.nth(i)
            raw = card.inner_text()
            item = parse_item(raw)
            if not item:
                continue
            if item["광고여부"] == "Y":
                # 광고(스폰서) 상품은 별도의 1~5위 번호를 달고 나와 실제 판매순위와
                # 겹치므로(둘 다 1위, 2위...) 판매순위 집계에서 제외한다.
                continue
            rank += 1
            if item["순위"] is None:
                item["순위"] = rank
            item["사이트"] = SITE
            item["카테고리"] = CATEGORY
            item["수집일"] = today

            href = card.locator("a.link_prdunit").first.get_attribute("href")
            item["링크"] = ("https://gift.kakao.com" + href) if href and href.startswith("/") else (href or "")
            item["이미지"] = card.locator("img.img_thumb").first.get_attribute("src") or ""

            rows.append(item)

        browser.close()

    if not rows:
        print("수집된 상품이 없습니다. 사이트 구조가 바뀌었을 수 있어요.")
        raise SystemExit(1)

    fieldnames = ["수집일", "사이트", "카테고리", "순위", "브랜드", "상품명", "가격", "광고여부", "링크", "이미지"]
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"저장 완료: {out_path} ({len(rows)}개 상품)")
    for r in rows[:10]:
        print(f"  {r['순위']:>2}위  {r['브랜드']:<12} {r['상품명'][:30]:<30} {r['가격']}원  광고:{r['광고여부']}")


if __name__ == "__main__":
    main()
