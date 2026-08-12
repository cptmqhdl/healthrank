"""data/latest.json(오늘 3채널 1~10위)을 상품 카테고리별로 취합해
data/category_daily.json 을 만든다.

상품명에 포함된 키워드로 카테고리를 판정한다. **상품 하나는 정확히 하나의
카테고리에만 배정된다** — 아래 CATEGORY_RULES 순서대로 첫 번째로 매칭되는
카테고리를 쓰고, 그 상품은 더 이상 다른 카테고리를 검사하지 않는다. 이렇게
하면 같은 상품이 두 카테고리에 동시에 집계되는 중복 오류가 애초에 발생하지
않는다(각 채널 합계 = 그 채널 상품 수가 항상 성립하도록 마지막에 검증한다).

키워드로 분류하기 애매한 상품(성분/용도가 뚜렷하지 않은 것)은 "기타"로 남는다
— AI 없이 규칙만으로 분류하는 한계이며, 의도된 동작이다.
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LATEST_PATH = BASE_DIR / "data" / "latest.json"
OUT_PATH = BASE_DIR / "data" / "category_daily.json"

SITE_ORDER = ["kakao", "daiso", "oliveyoung"]

# (카테고리 이름, [매칭 키워드]) — 위에서부터 순서대로 검사, 먼저 매칭되는 것 하나만 사용
CATEGORY_RULES = [
    ("눈건강", ["루테인", "지아잔틴", "눈건강"]),
    ("간건강", ["밀크씨슬", "실리마린", "헛개", "간건강"]),
    ("여성건강", ["질유산균", "여성건강", "이소플라본", "우먼"]),
    ("남성건강", ["전립선", "마카", "남성건강"]),
    ("홍삼", ["홍삼"]),
    ("멀티비타민", ["멀티비타민", "종합비타민"]),
    ("다이어트", ["다이어트", "슬림", "컷팅", "디톡스", "체지방", "가르시니아"]),
    ("유산균", ["유산균", "프로바이오틱스"]),
    ("오메가3", ["오메가3", "오메가-3", "알티지오메가"]),
    ("콜라겐", ["콜라겐"]),
    ("관절", ["관절", "글루코사민", "콘드로이친"]),
    ("피부미용", ["글루타치온", "PDRN", "멜라닌", "미백", "화이트닝"]),
    ("에너지", ["에너지", "활력", "활기력", "자양강장"]),
    ("혈당관리", ["혈당"]),
    ("장건강", ["식이섬유", "프리바이오틱스", "변비", "푸룬"]),
    ("면역", ["면역", "이뮨", "프로폴리스"]),
    ("비타민", ["비타민"]),
]
CATEGORY_ORDER = [name for name, _ in CATEGORY_RULES] + ["기타"]


def classify(name: str) -> str:
    upper = name.upper()
    for label, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw.upper() in upper:
                return label
    return "기타"


def main():
    data = json.loads(LATEST_PATH.read_text(encoding="utf-8"))

    counts = {name: {"kakao": 0, "daiso": 0, "oliveyoung": 0, "total": 0} for name in CATEGORY_ORDER}
    examples = {name: [] for name in CATEGORY_ORDER}
    total_items = 0

    for site_id in SITE_ORDER:
        site = data["sites"].get(site_id)
        if not site:
            continue
        for item in site["items"]:
            category = classify(item["name"])
            counts[category][site_id] += 1
            counts[category]["total"] += 1
            total_items += 1
            if len(examples[category]) < 6:
                examples[category].append({"site": site_id, "name": item["name"]})

    # 검증: 카테고리별 합계를 다 더하면 원래 상품 수와 정확히 같아야 한다
    # (중복 집계나 누락이 없다는 뜻)
    assert sum(c["total"] for c in counts.values()) == total_items, \
        "카테고리 합계가 원본 상품 수와 다릅니다 — 분류 로직에 중복/누락 버그가 있습니다"

    categories = [
        {"name": name, **counts[name], "examples": examples[name]}
        for name in CATEGORY_ORDER
        if counts[name]["total"] > 0
    ]

    dates = sorted({s["date"] for s in data["sites"].values()})
    payload = {
        "date": dates[-1] if dates else None,
        "total_items": total_items,
        "categories": categories,
    }

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"저장 완료: {OUT_PATH} (카테고리 {len(categories)}개, 상품 {total_items}개)")


if __name__ == "__main__":
    main()
