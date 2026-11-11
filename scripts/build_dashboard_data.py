"""data/raw/*.csv 를 읽어 대시보드(report.html)가 바로 쓸 수 있는 data/latest.json 을 만든다.

사이트별로 가장 최근 날짜의 데이터를 뽑고, 직전 수집일 데이터와 비교해 순위 변동
(▲▼-/NEW)을 계산한다.

2026-11-11 변경:
- 비교 기준을 상품명 → 링크 속 고유 상품번호로 변경. "[11월 올영픽]"처럼 프로모션
  문구만 바뀌어도 NEW로 잘못 표시되던 문제 수정 (월간 리포트와 같은 방식).
- 직전 수집일이 바로 전날이 아니면(수집 누락) 그 날짜를 prev_date로 기록해 화면에
  "N일 전 대비"로 보여준다.
"""

import json
from datetime import date

from common import BASE_DIR, SITES, product_key, read_csv, site_files

OUT_PATH = BASE_DIR / "data" / "latest.json"
TOP_N = 10


def build_site(site_id: str, label: str) -> dict | None:
    files = site_files(site_id)
    if not files:
        return None

    latest_date, latest_path = files[-1]
    latest_rows = read_csv(latest_path)
    collected_at = (latest_rows[0].get("수집시각") if latest_rows else None) or latest_date

    prev_rank: dict[str, int] = {}
    prev_date = None
    if len(files) >= 2:
        prev_date, prev_path = files[-2]
        for row in read_csv(prev_path):
            prev_rank[product_key(site_id, row)] = int(row["순위"])

    items = []
    for row in latest_rows:
        rank = int(row["순위"])
        if rank > TOP_N:
            continue
        key = product_key(site_id, row)
        before = prev_rank.get(key)
        if before is None:
            delta = {"type": "new", "value": None}
        elif before == rank:
            delta = {"type": "flat", "value": 0}
        elif before > rank:
            delta = {"type": "up", "value": before - rank}
        else:
            delta = {"type": "down", "value": rank - before}

        items.append({
            "key": key,
            "rank": rank,
            "brand": row.get("브랜드") or "",
            "name": row["상품명"],
            "price": int(row["가격"]),
            "ad": row.get("광고여부") == "Y",
            "link": row.get("링크") or "",
            "image": row.get("이미지") or "",
            "delta": delta,
        })

    items.sort(key=lambda x: x["rank"])
    gap_days = None
    if prev_date:
        gap_days = (date.fromisoformat(latest_date) - date.fromisoformat(prev_date)).days

    return {
        "id": site_id,
        "label": label,
        "date": collected_at,
        "prev_date": prev_date,
        "prev_gap_days": gap_days,
        "count": len(items),
        "items": items,
    }


def main():
    sites = {}
    for site_id, _prefix, label in SITES:
        result = build_site(site_id, label)
        if result:
            sites[site_id] = result

    payload = {
        "generated_from_dates": sorted({s["date"] for s in sites.values()}),
        "sites": sites,
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = ", ".join(f"{sid}:{s['count']}개" for sid, s in sites.items())
    print(f"저장 완료: {OUT_PATH} ({summary})")


if __name__ == "__main__":
    main()
