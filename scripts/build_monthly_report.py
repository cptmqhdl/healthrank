"""data/raw/*.csv 를 월별로 묶어 월간 판매순위 리포트용 JSON을 만든다.

사이트별로 그 달의 모든 날짜 파일을 모아 상품별 평균 순위·최다 1위 횟수·노출일수·
순위 변동(그 달 첫 관측일 대비 마지막 관측일)을 계산해 data/monthly/{YYYY-MM}.json
으로 저장한다. 사용 가능한 달 목록은 data/monthly/index.json 에 기록한다.

이 스크립트는 매일 자동 실행되므로, 이번 달 파일은 매일 최신 상태로 다시 계산되고
지난 달 파일은 그 달이 끝나는 순간부터 더 이상 갱신되지 않아 자연스럽게 "보관"된다
(별도의 아카이빙 로직이 필요 없음).

정확성을 위한 두 가지 보정:
1) 상품 식별: 상품명은 "[8월 올영픽]"처럼 프로모션 문구가 붙었다 빠졌다 해서
   같은 상품이 날짜마다 다른 이름으로 보일 수 있다. 링크에 들어있는 고유 상품번호
   (카카오 /product/숫자, 다이소 pdNo=, 올리브영 goodsNo=)를 추출해 진짜 식별자로
   쓰고, 이름/브랜드/가격/이미지는 가장 최근 날짜 값으로 표시한다.
2) "반짝 1위" 왜곡 방지: 하루만 반짝 1위 하고 사라진 상품이 한 달 내내 꾸준했던
   상품을 평균 순위로 제치지 않도록, 그 달 수집일의 최소 30%(최소 1일) 이상
   순위권에 들었던 상품만 TOP 10 후보로 인정한다.

알려진 한계: 다이소·올리브영 크롤러는 매일 1~10위까지만 수집하므로, 10~12위권을
넘나드는 상품은 순위 밖으로 밀린 날의 기록이 아예 없다(단순 결측이 아님). 그래서
이런 상품의 평균 순위는 실제보다 좋게 보일 수 있다. 카카오는 1~20위까지 수집해
이 영향이 상대적으로 적다.
"""

import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
OUT_DIR = BASE_DIR / "data" / "monthly"

# (사이트 id, 파일명 접두어, 화면에 보여줄 이름)
SITES = [
    ("kakao", "카카오선물하기", "카카오톡 선물하기"),
    ("daiso", "다이소몰", "다이소몰"),
    ("oliveyoung", "올리브영", "올리브영"),
]

MIN_APPEARANCE_RATIO = 0.3  # TOP 10 후보 자격: 수집일의 최소 30% 이상 랭크인

# 사이트별 링크에서 고유 상품번호를 뽑는 정규식 (실패하면 상품명으로 대체)
PRODUCT_ID_PATTERNS = {
    "kakao": re.compile(r"/product/(\d+)"),
    "daiso": re.compile(r"[?&]pdNo=([^&]+)"),
    "oliveyoung": re.compile(r"[?&]goodsNo=([^&]+)"),
}


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def product_key(site_id: str, row: dict) -> str:
    link = row.get("링크") or ""
    pattern = PRODUCT_ID_PATTERNS.get(site_id)
    if pattern:
        m = pattern.search(link)
        if m:
            return m.group(1)
    return "name:" + row["상품명"]  # 링크가 없거나 패턴이 안 맞으면 상품명으로 대체


def build_month_site(site_id: str, files_for_month: list[tuple[str, Path]]) -> dict:
    """files_for_month: [(date_str, path), ...] 오름차순 정렬된 목록."""
    products: dict[str, dict] = {}

    for date_str, path in files_for_month:
        for row in read_csv(path):
            rank = int(row["순위"])
            key = product_key(site_id, row)
            p = products.setdefault(key, {"ranks": [], "dates": []})
            p["ranks"].append(rank)
            p["dates"].append(date_str)
            # 날짜 오름차순으로 순회하므로, 마지막에 덮어써진 값이 가장 최근 값이 된다
            p["name"] = row["상품명"]
            p["brand"] = row.get("브랜드") or ""
            p["price"] = int(row["가격"])
            p["link"] = row.get("링크") or ""
            p["image"] = row.get("이미지") or ""

    days_collected = len(files_for_month)
    min_appearances = max(1, math.ceil(days_collected * MIN_APPEARANCE_RATIO))

    items = []
    for p in products.values():
        ranks = p["ranks"]
        appearances = len(ranks)
        if appearances < min_appearances:
            continue

        avg_rank = round(sum(ranks) / appearances, 1)
        first_rank, last_rank = ranks[0], ranks[-1]
        if appearances >= 2 and first_rank != last_rank:
            delta = (
                {"type": "up", "value": first_rank - last_rank}
                if first_rank > last_rank
                else {"type": "down", "value": last_rank - first_rank}
            )
        else:
            delta = {"type": "flat", "value": 0}

        items.append({
            "name": p["name"],
            "brand": p["brand"],
            "price": p["price"],
            "link": p["link"],
            "image": p["image"],
            "avg_rank": avg_rank,
            "best_rank": min(ranks),
            "top1_days": sum(1 for r in ranks if r == 1),
            "appearances": appearances,
            "delta": delta,
        })

    # 평균 순위가 좋은 순, 동률이면 더 자주 노출된(꾸준한) 상품이 우선
    items.sort(key=lambda x: (x["avg_rank"], -x["appearances"]))

    return {
        "days_collected": days_collected,
        "date_range": [files_for_month[0][0], files_for_month[-1][0]],
        "items": items,
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # site_id -> "YYYY-MM" -> [(date_str, path), ...]
    by_site_month: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for site_id, prefix, _label in SITES:
        for path in sorted(RAW_DIR.glob(f"{prefix}_*.csv")):
            date_str = path.stem.replace(f"{prefix}_", "")
            by_site_month[site_id][date_str[:7]].append((date_str, path))

    months = sorted({m for site_months in by_site_month.values() for m in site_months})

    for month in months:
        payload = {"month": month, "sites": {}}
        for site_id, _prefix, label in SITES:
            files_for_month = sorted(by_site_month[site_id].get(month, []))
            if not files_for_month:
                continue
            site_result = build_month_site(site_id, files_for_month)
            site_result["id"] = site_id
            site_result["label"] = label
            payload["sites"][site_id] = site_result

        out_path = OUT_DIR / f"{month}.json"
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    (OUT_DIR / "index.json").write_text(
        json.dumps({"months": months}, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"월간 리포트 생성 완료: {len(months)}개월 ({', '.join(months)})")


if __name__ == "__main__":
    main()
