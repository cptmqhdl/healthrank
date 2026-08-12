"""다이소몰 - 랭킹 페이지의 '식품' 카테고리 크롤러 (프로토타입).

다이소몰 랭킹 페이지에는 건강기능식품 전용 필터가 없어, 가장 가까운 상위 카테고리인
'식품'을 기준으로 수집한다 (실제로 상위권 대부분이 홍삼/유산균/비타민 등 건강 관련 식품).

실행하면 오늘 날짜로 data/raw/다이소몰_YYYY-MM-DD.csv 파일을 만든다.
"""

import csv
import re
from datetime import date
from pathlib import Path

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

SITE = "다이소몰"
CATEGORY = "식품"
URL = "https://www.daisomall.co.kr/ds/rank/new"

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "data" / "raw"

# "현재 순위\n1\n(급상승\n)?장바구니\n담기\n(NEW\n)?12,345\n원\n상품명\n택배배송..." 형태를 그대로 파싱
ITEM_RE = re.compile(
    r"현재 순위\n(\d+)\n"
    r"(?:급상승\n)?"
    r"장바구니\n담기\n"
    r"(?:NEW\n)?"
    r"([\d,]+)\n원\n"
    r"([^\n]+)"
)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    out_path = OUT_DIR / f"{SITE}_{today}.csv"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=UA, locale="ko-KR", viewport={"width": 1400, "height": 1000})
        page = context.new_page()

        page.goto(URL, timeout=20000, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        page.get_by_role("button", name=CATEGORY, exact=True).click(timeout=8000)
        page.wait_for_timeout(2500)

        text = page.inner_text("body")
        browser.close()

    matches = ITEM_RE.findall(text)
    print(f"발견된 상품 수: {len(matches)}")

    rows = []
    for rank, price, name in matches:
        rows.append({
            "수집일": today,
            "사이트": SITE,
            "카테고리": CATEGORY,
            "순위": rank,
            "브랜드": "",
            "상품명": name.strip(),
            "가격": price.replace(",", ""),
        })

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
        print(f"  {r['순위']:>2}위  {r['상품명'][:35]:<35} {r['가격']}원")


if __name__ == "__main__":
    main()
