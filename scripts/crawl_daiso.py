"""다이소몰 - '건강식품' 카테고리 페이지의 '건강식품 카테고리별 랭킹' 위젯 크롤러.

이 위젯은 화면에 그려지기 전에 내부적으로 fapi.daisomall.co.kr의 랭킹 API를
호출해 데이터를 받아온다. 예전에는 Playwright로 실제 화면을 렌더링하고 위젯이
보일 때까지 스크롤해서 DOM을 읽었는데, 이 위젯이 페이지 하단에 있어 스크롤/렌더링
타이밍이 매번 달라 GitHub Actions에서 반복적으로 타임아웃이 났다(2026-08-15/16/18/19
전부 이 방식으로 실패). 위젯이 쓰는 API를 직접 호출하면 브라우저 렌더링 없이
바로 같은 데이터를 받을 수 있어 이 문제가 근본적으로 사라진다(같은 시각에 두
방식으로 수집해 순위 1~10위가 정확히 일치함을 확인함).

실행하면 오늘 날짜로 data/raw/다이소몰_YYYY-MM-DD.csv 파일을 만든다.
"""

import csv
import html
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

SITE = "다이소몰"
CATEGORY = "건강식품"
# 화면의 "건강식품 카테고리별 랭킹" 위젯이 내부적으로 호출하는 API.
API_URL = "https://fapi.daisomall.co.kr/pd/rank/list"
PRODUCT_URL_TMPL = "https://www.daisomall.co.kr/pd/pdr/SCR_PDR_0001?pdNo={pd_no}&recmYn=N"
CDN_HOST = "https://cdn.daisomall.co.kr"
TOP_N = 10
KST = timezone(timedelta(hours=9))

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "data" / "raw"


def build_image_url(pd_img_url: str) -> str:
    """API가 주는 원본 이미지 경로(/file/PD/YYYYMMDD/파일명)를 화면에서 쓰는
    썸네일 CDN 주소(cdn.daisomall.co.kr/file/resize/.../thumb/300/파일명)로 바꾼다."""
    if not pd_img_url:
        return ""
    parts = pd_img_url.strip("/").split("/")
    if len(parts) < 2 or parts[0] != "file":
        return CDN_HOST + pd_img_url
    filename = parts[-1]
    middle = parts[1:-1]
    new_path = "/file/resize/" + "/".join(middle) + "/thumb/300/" + filename
    return CDN_HOST + new_path


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    collected_at = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    out_path = OUT_DIR / f"{SITE}_{today}.csv"

    payload = {
        "mallId": "MALL_BH",
        "pageNum": 1,
        "cntPerPage": TOP_N,
        "rankTy": ["1", "2"],
        "newPdYn": "Y",
        "lclCtgrNo": ["BH_CTGR_00013"],
    }
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.daisomall.co.kr",
        "Referer": "https://www.daisomall.co.kr/",
    }

    resp = requests.post(API_URL, json=payload, headers=headers, timeout=20)
    resp.raise_for_status()
    items = resp.json().get("data", {}).get("list", [])
    print(f"발견된 상품 수: {len(items)}")

    rows = []
    for rank, item in enumerate(items[:TOP_N], start=1):
        pd_no = item.get("pdNo") or ""
        name = html.unescape((item.get("exhPdNm") or "").strip())
        price = item.get("pdPrc")
        if not (pd_no and name and price is not None):
            continue

        rows.append({
            "수집일": today,
            "수집시각": collected_at,
            "사이트": SITE,
            "카테고리": CATEGORY,
            "순위": rank,
            "브랜드": "",
            "상품명": name,
            "가격": str(price),
            "링크": PRODUCT_URL_TMPL.format(pd_no=pd_no),
            "이미지": build_image_url(item.get("pdImgUrl") or ""),
        })

    if not rows:
        print("수집된 상품이 없습니다. 사이트 구조가 바뀌었을 수 있어요.")
        raise SystemExit(1)

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
