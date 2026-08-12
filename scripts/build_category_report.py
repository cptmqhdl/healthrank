"""data/latest.json(오늘 3채널 1~10위)을 상품 카테고리별로 취합해
data/category_daily.json 을 만든다.

상품명에 포함된 키워드로 카테고리를 판정한다. **상품 하나는 정확히 하나의
카테고리에만 배정된다** — 아래 CATEGORY_RULES 순서대로 첫 번째로 매칭되는
카테고리를 쓰고, 그 상품은 더 이상 다른 카테고리를 검사하지 않는다. 이렇게
하면 같은 상품이 두 카테고리에 동시에 집계되는 중복 오류가 애초에 발생하지
않는다(각 채널 합계 = 그 채널 상품 수가 항상 성립하도록 마지막에 검증한다).

키워드로 분류하기 애매한 상품(성분/용도가 뚜렷하지 않은 것)은 "기타"로 남는다
— AI 없이 규칙만으로 분류하는 한계이며, 의도된 동작이다.

날마다 순위가 바뀌면서 CATEGORY_RULES에 없는 새로운 유형의 상품이 계속
"기타"에 쌓일 수 있다. 이걸 사람이 놓치지 않도록, 최근 며칠간의 "기타" 상품
이름에서 반복적으로 등장하는 단어를 자동으로 뽑아 "카테고리 후보 키워드"로
같이 보여준다(완전 자동 분류는 아니고, 사람이 보고 필요하면 CATEGORY_RULES에
한 줄 추가하는 식의 힌트다).
"""

import csv
import json
import re
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LATEST_PATH = BASE_DIR / "data" / "latest.json"
RAW_DIR = BASE_DIR / "data" / "raw"
OUT_PATH = BASE_DIR / "data" / "category_daily.json"

SITE_ORDER = ["kakao", "daiso", "oliveyoung"]
SITE_PREFIX = {"kakao": "카카오선물하기", "daiso": "다이소몰", "oliveyoung": "올리브영"}

# 최근 며칠치 "기타" 상품에서 후보 키워드를 뽑을지
LOOKBACK_DAYS = 14
# 이 이상 반복돼야 후보로 인정 (서로 다른 상품 기준)
MIN_KEYWORD_COUNT = 3
MAX_SUGGESTIONS = 8

# 카카오/다이소/올리브영 링크에서 고유 상품번호를 뽑는 정규식 (월간 리포트와 동일한 방식) —
# 같은 상품이 여러 날 반복 노출돼도 후보 키워드 집계에서 한 번만 세기 위함
PRODUCT_ID_PATTERNS = {
    "kakao": re.compile(r"/product/(\d+)"),
    "daiso": re.compile(r"[?&]pdNo=([^&]+)"),
    "oliveyoung": re.compile(r"[?&]goodsNo=([^&]+)"),
}

# 카테고리 신호가 아닌 마케팅/공통 문구 — 후보 키워드에서 제외
KEYWORD_STOPWORDS = {
    "증정", "선물", "기획", "단독", "에디션", "프리미엄", "이벤트", "리뷰", "한정",
    "패키지", "박스", "세트", "할인", "특가", "공식", "수입", "국내산", "제품", "상품",
    "고급", "신상", "베스트", "인기", "추천", "기본", "일반", "스페셜", "스탠다드",
    "정품", "본품", "증량", "리필", "교환", "선택", "가능", "올영픽", "올리브영",
    "다이소몰", "카카오",
    # 기간/용량 단위어 — 특정 성분·용도가 아니라 그냥 며칠분/몇 개짜리인지를 나타낼 뿐
    "일분", "개월분", "주분", "년분", "회분",
    # 제형(먹는 형태) 단어 — 카테고리(용도)가 아니라 알약이냐 젤리냐 같은 형태 정보라 제외
    "젤리", "캡슐", "츄어블", "구미", "필름", "스틱", "파우치", "타블렛", "분말",
}

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


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def product_key(site_id: str, row: dict) -> str:
    """월간 리포트와 같은 방식으로 상품 고유번호를 뽑는다 — 같은 상품이 여러 날
    반복 노출돼도 후보 키워드 집계에서 한 번만 세기 위함."""
    link = row.get("링크") or ""
    pattern = PRODUCT_ID_PATTERNS.get(site_id)
    if pattern:
        m = pattern.search(link)
        if m:
            return m.group(1)
    return "name:" + row.get("상품명", "")


def tokenize(name: str) -> set:
    return {t for t in re.findall(r"[가-힣]{2,}", name) if t not in KEYWORD_STOPWORDS}


def suggest_keywords() -> list[dict]:
    """최근 LOOKBACK_DAYS일치 데이터에서 '기타'로 분류된 상품들을 모아, 반복적으로
    등장하는 단어를 카테고리 후보 키워드로 뽑는다. 완전 자동 분류가 아니라
    "이 단어들이 자주 보이니 카테고리 추가를 검토해보라"는 힌트를 만드는 것이다."""
    seen_products = {}  # (site_id, product_key) -> {"name", "site", "tokens"}

    for site_id in SITE_ORDER:
        prefix = SITE_PREFIX[site_id]
        files = sorted(RAW_DIR.glob(f"{prefix}_*.csv"))[-LOOKBACK_DAYS:]
        for path in files:
            for row in read_csv(path):
                name = row.get("상품명")
                if not name or classify(name) != "기타":
                    continue
                key = (site_id, product_key(site_id, row))
                if key not in seen_products:
                    seen_products[key] = {"name": name, "site": site_id, "tokens": tokenize(name)}

    token_counts = Counter()
    token_examples: dict[str, list[str]] = {}
    for info in seen_products.values():
        for tok in info["tokens"]:
            token_counts[tok] += 1
            token_examples.setdefault(tok, []).append(info["name"])

    suggestions = []
    for tok, count in token_counts.most_common():
        if count < MIN_KEYWORD_COUNT:
            break
        suggestions.append({"keyword": tok, "count": count, "examples": token_examples[tok][:3]})
        if len(suggestions) >= MAX_SUGGESTIONS:
            break
    return suggestions


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
    categories.sort(key=lambda c: c["total"], reverse=True)

    keyword_suggestions = suggest_keywords()

    dates = sorted({s["date"] for s in data["sites"].values()})
    payload = {
        "date": dates[-1] if dates else None,
        "total_items": total_items,
        "categories": categories,
        "keyword_suggestions": keyword_suggestions,
    }

    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"저장 완료: {OUT_PATH} (카테고리 {len(categories)}개, 상품 {total_items}개, "
        f"후보 키워드 {len(keyword_suggestions)}개)"
    )


if __name__ == "__main__":
    main()
