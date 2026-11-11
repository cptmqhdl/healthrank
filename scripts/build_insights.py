"""data/raw/*.csv 전체(수집 첫날부터)를 읽어 추세·분석용 data/insights.json 을 만든다.

담는 내용
1) health      — 채널별 수집 상태 (마지막 수집일, 최근 30일 수집률, 누락일)
2) products    — 1~10위에 한 번이라도 든 상품의 일별 순위 기록 (상품 순위 추이 그래프용)
3) movers      — 채널별 급상승 / 신규 진입 / 이탈 (최근 3회 수집 vs 그 전 7회 수집)
4) category_weekly — 주별 카테고리 비중 (카테고리 흐름 히트맵용)
5) promo       — 판촉 방식 분석 (최근 30일 순위권 내 비중, 같은 상품 문구 有/無 비교)
6) cross_channel — 여러 채널 동시 진입 브랜드 (최근 7일)

상품 식별은 월간 리포트와 같이 링크 속 고유번호를 쓴다. 순위는 모든 채널 1~10위
기준(카카오는 20위까지 수집하지만 채널 간 비교를 위해 10위로 맞춤). 10위 밖은
"권외"이며 데이터가 없다 — 그래서 '이탈'은 "11위 이하로 밀림"을 뜻한다.
"""

import json
from collections import defaultdict
from datetime import date, timedelta

from common import (BASE_DIR, CATEGORY_ORDER, EXTRA_BRANDS, PROMO_ORDER, SITE_LABEL, SITES,
                    brand_of, classify, kst_today, normalize_brand, product_key, promo_tags,
                    read_csv, site_files)

OUT_PATH = BASE_DIR / "data" / "insights.json"
TOP_N = 10
OUT_RANK = TOP_N + 1  # 권외를 평균 낼 때 쓰는 가상 순위

RECENT_N = 3       # 급상승/이탈 판정: 최근 수집 3회
BASE_N = 7         # 비교 기준: 그 전 수집 7회
NEW_WINDOW_N = 7   # 신규 진입: 최근 수집 7회 안에 처음(또는 오랜만에) 등장
REENTRY_GAP_N = 14 # 이 횟수 이상 안 보이다 다시 나타나면 "재진입"
PROMO_DAYS = 30
CROSS_WINDOWS = [7, 30]  # 동시 진입: 최근 7일 / 30일 두 가지


def load():
    known_brands = set(EXTRA_BRANDS)
    raw = {}
    for site_id, _p, _l in SITES:
        raw[site_id] = []
        for d, path in site_files(site_id):
            rows = [r for r in read_csv(path) if int(r["순위"]) <= TOP_N]
            raw[site_id].append((d, rows))
            for r in rows:
                b = normalize_brand(r.get("브랜드") or "")
                if b:
                    known_brands.add(b)
    return raw, known_brands


def build():
    raw, known_brands = load()
    all_dates = sorted({d for site in raw.values() for d, _ in site})
    date_idx = {d: i for i, d in enumerate(all_dates)}
    today = kst_today()

    products = {}            # pid -> info
    by_site_day = {}         # site -> [(date, {pid: rank})]
    day_names = defaultdict(dict)  # pid -> {date: name}  (판촉 문구 有/無 비교용)

    for site_id, days in raw.items():
        by_site_day[site_id] = []
        for d, rows in days:
            ranks = {}
            for r in rows:
                pid = f"{site_id}:{product_key(site_id, r)}"
                rank = int(r["순위"])
                ranks[pid] = rank
                p = products.setdefault(pid, {"site": site_id, "series": []})
                p["series"].append([date_idx[d], rank])
                p.update({
                    "name": r["상품명"], "price": int(r["가격"]),
                    "link": r.get("링크") or "", "image": r.get("이미지") or "",
                    "brand": brand_of(site_id, r, known_brands),
                })
                day_names[pid][d] = r["상품명"]
            by_site_day[site_id].append((d, ranks))

    for pid, p in products.items():
        rs = [r for _, r in p["series"]]
        p["category"] = classify(p["name"])
        p["first"] = all_dates[p["series"][0][0]]
        p["last"] = all_dates[p["series"][-1][0]]
        p["days"] = len(rs)
        p["best"] = min(rs)
        p["avg"] = round(sum(rs) / len(rs), 1)

    return {
        "generated_at": today,
        "dates": all_dates,
        # 채널별로 실제 수집한 날짜(dates 인덱스) — 그날 순위에 없으면 '권외', 아예 수집을
        # 못 한 날이면 '데이터 없음'으로 구분하기 위함
        "site_dates": {s: [date_idx[d] for d, _ in by_site_day[s]] for s in by_site_day},
        "health": build_health(by_site_day, today),
        "products": products,
        "movers": {s: build_movers(by_site_day[s], products) for s in by_site_day},
        "category_weekly": build_category_weekly(by_site_day, products),
        "promo": build_promo(by_site_day, products, day_names, all_dates[-1]),
        "cross_channel": build_cross(by_site_day, products, all_dates),
    }


# ---------------------------------------------------------------------------
def build_health(by_site_day, today):
    # 30일 창은 "가장 최근 수집일"에서 끝낸다 — 오늘 수집 전에 계산해도 오늘이
    # 누락으로 잡히지 않게. 오늘 기준 며칠 묵었는지는 stale_days로 따로 본다.
    t = date.fromisoformat(today)
    ref = max(date.fromisoformat(days[-1][0]) for days in by_site_day.values() if days)
    window = [(ref - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
    out = {}
    for site_id, days in by_site_day.items():
        have = {d for d, _ in days}
        last = days[-1][0] if days else None
        out[site_id] = {
            "label": SITE_LABEL[site_id],
            "first_date": days[0][0] if days else None,
            "last_date": last,
            "total_days": len(days),
            "days_30": sum(1 for d in window if d in have),
            "missing_30": [d for d in window if d not in have],
            "stale_days": (t - date.fromisoformat(last)).days if last else None,
        }
    return out


# ---------------------------------------------------------------------------
def build_movers(days, products):
    if len(days) < RECENT_N + 2:
        return {"rising": [], "new": [], "dropped": [], "window": None}
    recent = days[-RECENT_N:]
    base = days[-(RECENT_N + BASE_N):-RECENT_N]
    latest = days[-1][1]

    def avg(pid, win):
        return sum(r.get(pid, OUT_RANK) for _, r in win) / len(win)

    def seen_in(pid, win):
        return sum(1 for _, r in win if pid in r)

    rising = []
    for pid, rank in latest.items():
        if seen_in(pid, base) == 0:
            continue  # 기준 기간에 아예 없었으면 '신규'로 분류
        diff = avg(pid, base) - avg(pid, recent)
        if diff >= 2:
            rising.append({"pid": pid, "rank": rank, "from": round(avg(pid, base), 1),
                           "to": round(avg(pid, recent), 1), "gain": round(diff, 1)})
    rising.sort(key=lambda x: -x["gain"])

    new = []
    new_window = days[-NEW_WINDOW_N:]
    for pid, rank in latest.items():
        first_pos = next(i for i, (_, r) in enumerate(days) if pid in r)
        idx_in_days = [i for i, (_, r) in enumerate(days) if pid in r]
        # 최근 7회 안에서 처음 나타난 시점
        start = len(days) - len(new_window)
        recent_hits = [i for i in idx_in_days if i >= start]
        before_hits = [i for i in idx_in_days if i < start]
        if not recent_hits:
            continue
        if first_pos >= start:
            kind = "첫 진입"
        elif before_hits and recent_hits[0] - before_hits[-1] > REENTRY_GAP_N:
            kind = "재진입"
        else:
            continue
        new.append({"pid": pid, "rank": rank, "kind": kind, "since": days[recent_hits[0]][0]})
    new.sort(key=lambda x: x["rank"])

    dropped = []
    for pid in {p for _, r in base for p in r}:
        if seen_in(pid, base) >= 4 and seen_in(pid, recent) == 0:
            last_seen = max(d for d, r in base if pid in r)
            dropped.append({"pid": pid, "from": round(sum(r[pid] for _, r in base if pid in r) / seen_in(pid, base), 1),
                            "last_seen": last_seen})
    dropped.sort(key=lambda x: x["from"])

    return {
        "rising": rising[:6], "new": new[:6], "dropped": dropped[:6],
        "window": {"recent": [recent[0][0], recent[-1][0]], "base": [base[0][0], base[-1][0]]},
    }


# ---------------------------------------------------------------------------
def week_start(d: str) -> str:
    x = date.fromisoformat(d)
    return (x - timedelta(days=x.weekday())).isoformat()


def build_category_weekly(by_site_day, products):
    weeks = sorted({week_start(d) for days in by_site_day.values() for d, _ in days})
    widx = {w: i for i, w in enumerate(weeks)}
    # slots[cat][site][week] = 그 주 1~10위 자리 합계, ndays[site][week] = 수집일수
    slots = defaultdict(lambda: defaultdict(lambda: [0] * len(weeks)))
    ndays = {s: [0] * len(weeks) for s in by_site_day}
    for site_id, days in by_site_day.items():
        for d, ranks in days:
            w = widx[week_start(d)]
            ndays[site_id][w] += 1
            for pid in ranks:
                slots[products[pid]["category"]][site_id][w] += 1
    totals = {c: sum(sum(v) for v in slots[c].values()) for c in slots}
    cats = sorted(slots, key=lambda c: (c == "기타", -totals[c]))
    return {
        "weeks": weeks,
        "days": ndays,
        "categories": [{"name": c, "slots": {s: slots[c][s] for s in by_site_day}} for c in cats],
    }


# ---------------------------------------------------------------------------
def build_promo(by_site_day, products, day_names, today):
    cutoff = (date.fromisoformat(today) - timedelta(days=PROMO_DAYS - 1)).isoformat()
    tags_of = {}  # (pid, date) -> tags

    def tags(pid, d):
        k = (pid, d)
        if k not in tags_of:
            tags_of[k] = promo_tags(day_names[pid].get(d, ""))
        return tags_of[k]

    def summarize(site_ids):
        obs = [(pid, d, rank) for s in site_ids for d, ranks in by_site_day[s] if d >= cutoff
               for pid, rank in ranks.items()]
        total = len(obs)
        rows = []
        for tag in PROMO_ORDER + ["판촉 문구 없음"]:
            if tag == "판촉 문구 없음":
                hit = [o for o in obs if not tags(o[0], o[1])]
            else:
                hit = [o for o in obs if tag in tags(o[0], o[1])]
            miss = [o for o in obs if tag not in tags(o[0], o[1])] if tag != "판촉 문구 없음" else []
            if not hit:
                rows.append({"tag": tag, "share": 0, "products": 0})
                continue
            distinct = {}
            for pid, d, rank in hit:
                if pid not in distinct or rank < distinct[pid][1]:
                    distinct[pid] = (day_names[pid][d], rank)
            ex = sorted(distinct.items(), key=lambda kv: kv[1][1])[:3]
            rows.append({
                "tag": tag,
                "share": round(len(hit) / total * 100, 1) if total else 0,
                "products": len(distinct),
                "avg_rank": round(sum(o[2] for o in hit) / len(hit), 1),
                "avg_rank_without": round(sum(o[2] for o in miss) / len(miss), 1) if miss else None,
                "examples": [{"pid": pid, "name": nm} for pid, (nm, _r) in ex],
            })
        return {"slots": total, "rows": rows}

    site_ids = list(by_site_day)
    result = {"window": [cutoff, today], "all": summarize(site_ids)}
    for s in site_ids:
        result[s] = summarize([s])

    # 같은 상품인데 날짜에 따라 판촉 문구가 붙었다 떨어졌다 한 경우 → 문구 有/無 순위 비교
    # (전체 기간). 상품 자체 인기 차이를 빼고 문구 효과만 어느 정도 볼 수 있다.
    rank_on = {(pid, d): rank for s in site_ids for d, ranks in by_site_day[s]
               for pid, rank in ranks.items()}
    paired = []
    for tag in PROMO_ORDER:
        diffs = []
        for pid in products:
            on, off = [], []
            for d in day_names[pid]:
                (on if tag in tags(pid, d) else off).append(rank_on[(pid, d)])
            if len(on) >= 2 and len(off) >= 2:
                diffs.append(sum(off) / len(off) - sum(on) / len(on))
        if len(diffs) >= 3:
            paired.append({"tag": tag, "products": len(diffs),
                           "gain": round(sum(diffs) / len(diffs), 1),
                           "better": sum(1 for x in diffs if x > 0)})
    result["paired"] = paired
    return result


# ---------------------------------------------------------------------------
def build_cross(by_site_day, products, all_dates):
    return {f"d{n}": build_cross_window(by_site_day, products, all_dates, n) for n in CROSS_WINDOWS}


def build_cross_window(by_site_day, products, all_dates, days_back):
    last = all_dates[-1]
    cutoff = (date.fromisoformat(last) - timedelta(days=days_back - 1)).isoformat()

    brand_site = defaultdict(lambda: defaultdict(dict))  # brand -> site -> pid -> best rank
    for site_id, days in by_site_day.items():
        for d, ranks in days:
            if d < cutoff:
                continue
            for pid, rank in ranks.items():
                b = products[pid]["brand"]
                if not b:
                    continue
                cur = brand_site[b][site_id].get(pid)
                brand_site[b][site_id][pid] = min(rank, cur) if cur else rank

    # 브랜드가 같은 날 2개 이상 채널 1~10위에 동시에 있었던 날 수 (전체 기간)
    co_days = defaultdict(int)
    first_co = {}
    present_by_day = defaultdict(lambda: defaultdict(set))  # date -> brand -> sites
    for site_id, days in by_site_day.items():
        for d, ranks in days:
            for pid in ranks:
                if products[pid]["brand"]:
                    present_by_day[d][products[pid]["brand"]].add(site_id)
    for d in all_dates:
        for b, ss in present_by_day[d].items():
            if len(ss) >= 2:
                co_days[b] += 1
                first_co.setdefault(b, d)

    out = []
    for b, sites in brand_site.items():
        if len(sites) < 2:
            continue
        out.append({
            "brand": b,
            "sites": {s: [{"pid": pid, "best": r} for pid, r in sorted(v.items(), key=lambda kv: kv[1])]
                      for s, v in sites.items()},
            "n_sites": len(sites),
            "score": sum(min(v.values()) for v in sites.values()),
            "co_days": co_days.get(b, 0),
            "since": first_co.get(b),
        })
    out.sort(key=lambda x: (-x["n_sites"], x["score"]))

    # 같은 카테고리가 3채널 모두 1~10위에 있는지 (최근 7일)
    cat_sites = defaultdict(lambda: defaultdict(set))
    for site_id, days in by_site_day.items():
        for d, ranks in days:
            if d >= cutoff:
                for pid in ranks:
                    cat_sites[products[pid]["category"]][site_id].add(pid)
    cats = [{"name": c, "sites": {s: len(v) for s, v in ss.items()}}
            for c, ss in cat_sites.items() if c != "기타" and len(ss) >= 2]
    cats.sort(key=lambda x: (-len(x["sites"]), -sum(x["sites"].values())))
    return {"window": [cutoff, last], "brands": out, "categories": cats}


def main():
    data = build()
    OUT_PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    kb = OUT_PATH.stat().st_size / 1024
    print(f"저장 완료: {OUT_PATH} ({kb:.0f}KB, 상품 {len(data['products'])}개, "
          f"동시 진입 브랜드 7일 {len(data['cross_channel']['d7']['brands'])}개 / "
          f"30일 {len(data['cross_channel']['d30']['brands'])}개)")


if __name__ == "__main__":
    main()
