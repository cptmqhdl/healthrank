"""data/raw/*.csv 를 읽어 대시보드(report.html)가 바로 쓸 수 있는 data/latest.json 을 만든다.

사이트별로 가장 최근 날짜의 데이터를 뽑고, 그 전날 데이터가 있으면 상품명을 기준으로
순위 변동(▲▼-/NEW)을 계산한다. 전날 데이터가 없으면(수집 첫날 등) 전부 NEW로 표시한다.
"""

import csv
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
OUT_PATH = BASE_DIR / "data" / "latest.json"

# (사이트 id, 파일명 접두어, 화면에 보여줄 이름)
SITES = [
    ("kakao", "카카오선물하기", "카카오톡 선물하기"),
    ("daiso", "다이소몰", "다이소몰"),
    ("oliveyoung", "올리브영", "올리브영"),
]

# 대시보드에는 사이트별 1~10위까지만 보여준다 (크롤러는 더 많이 수집해도 화면 노출은 10위까지)
TOP_N = 10


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build_site(site_id: str, prefix: str, label: str) -> dict | None:
    files = sorted(RAW_DIR.glob(f"{prefix}_*.csv"))
    if not files:
        return None

    latest_path = files[-1]
    latest_date = latest_path.stem.replace(f"{prefix}_", "")
    latest_rows = read_csv(latest_path)

    prev_by_name: dict[str, int] = {}
    if len(files) >= 2:
        prev_rows = read_csv(files[-2])
        for row in prev_rows:
            prev_by_name[row["상품명"]] = int(row["순위"])

    items = []
    for row in latest_rows:
        rank = int(row["순위"])
        if rank > TOP_N:
            continue
        name = row["상품명"]
        prev_rank = prev_by_name.get(name)

        if prev_rank is None:
            delta = {"type": "new", "value": None}
        elif prev_rank == rank:
            delta = {"type": "flat", "value": 0}
        elif prev_rank > rank:
            delta = {"type": "up", "value": prev_rank - rank}
        else:
            delta = {"type": "down", "value": rank - prev_rank}

        items.append(
            {
                "rank": rank,
                "brand": row.get("브랜드") or "",
                "name": name,
                "price": int(row["가격"]),
                "ad": row.get("광고여부") == "Y",
                "link": row.get("링크") or "",
                "image": row.get("이미지") or "",
                "delta": delta,
            }
        )

    items.sort(key=lambda x: x["rank"])

    return {
        "id": site_id,
        "label": label,
        "date": latest_date,
        "count": len(items),
        "items": items,
    }


def main():
    sites = {}
    for site_id, prefix, label in SITES:
        result = build_site(site_id, prefix, label)
        if result:
            sites[site_id] = result

    dates = [s["date"] for s in sites.values()]
    payload = {
        "generated_from_dates": sorted(set(dates)),
        "sites": sites,
    }

    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = ", ".join(f"{site_id}:{s['count']}개" for site_id, s in sites.items())
    print(f"저장 완료: {OUT_PATH} ({summary})")


if __name__ == "__main__":
    main()
