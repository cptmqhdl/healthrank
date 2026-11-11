"""여러 스크립트가 같이 쓰는 공통 규칙 모음.

- 사이트 정의, CSV 읽기, 상품 고유번호 추출
- 상품명 → 카테고리 분류 (추세 리포트의 "카테고리 흐름"에 사용)
- 브랜드 정규화 (여러 채널 동시 진입 판정에 사용 — 다이소는 브랜드 컬럼이 비어 있어
  상품명에서 추출)
- 상품명 → 판촉 방식 태그 (판촉 방식 분석에 사용)
- 한국시간(KST) 날짜 — 깃허브 서버는 UTC라 date.today()를 쓰면 한국 날짜와 어긋날 수 있음
"""

import csv
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
KST = timezone(timedelta(hours=9))

# (사이트 id, 파일명 접두어, 화면에 보여줄 이름)
SITES = [
    ("kakao", "카카오선물하기", "카카오톡 선물하기"),
    ("daiso", "다이소몰", "다이소몰"),
    ("oliveyoung", "올리브영", "올리브영"),
]
SITE_PREFIX = {sid: prefix for sid, prefix, _ in SITES}
SITE_LABEL = {sid: label for sid, _, label in SITES}

PRODUCT_ID_PATTERNS = {
    "kakao": re.compile(r"/product/(\d+)"),
    "daiso": re.compile(r"[?&]pdNo=([^&]+)"),
    "oliveyoung": re.compile(r"[?&]goodsNo=([^&]+)"),
}


def kst_now() -> datetime:
    return datetime.now(KST)


def kst_today() -> str:
    return kst_now().date().isoformat()


MIN_ROWS = 10  # 하루치로 인정하는 최소 상품 수 (세 사이트 모두 1~10위 수집)


def already_collected(out_path: Path) -> bool:
    """오늘 파일이 이미 제대로(10개 이상) 있으면 True — 하루에 여러 번 예약 실행돼도
    이미 성공한 사이트는 다시 긁지 않는다. --force 로 무시 가능."""
    import sys
    if "--force" in sys.argv or not out_path.exists():
        return False
    try:
        return len(read_csv(out_path)) >= MIN_ROWS
    except Exception:
        return False


def with_retry(fn, attempts: int = 3, wait_sec: int = 20, label: str = ""):
    """fn()을 최대 attempts번 시도. 예외가 나거나 결과가 MIN_ROWS개 미만이면 재시도.
    카카오가 9~10월에 열흘에 한 번꼴로 실패하던 것(페이지 로딩 지연으로 추정)을 막기 위함."""
    import time
    last_err = None
    for i in range(1, attempts + 1):
        try:
            rows = fn()
            if rows and len(rows) >= MIN_ROWS:
                return rows
            last_err = RuntimeError(f"상품이 {len(rows or [])}개만 수집됨")
        except Exception as e:  # noqa: BLE001
            last_err = e
        print(f"[{label}] {i}/{attempts}차 시도 실패: {last_err}")
        if i < attempts:
            time.sleep(wait_sec * i)
    raise SystemExit(f"[{label}] {attempts}번 모두 실패: {last_err}")


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def site_files(site_id: str) -> list[tuple[str, Path]]:
    """[(YYYY-MM-DD, path), ...] 날짜 오름차순."""
    prefix = SITE_PREFIX[site_id]
    out = []
    for path in RAW_DIR.glob(f"{prefix}_*.csv"):
        out.append((path.stem.replace(f"{prefix}_", ""), path))
    return sorted(out)


def product_key(site_id: str, row: dict) -> str:
    link = row.get("링크") or ""
    pattern = PRODUCT_ID_PATTERNS.get(site_id)
    if pattern:
        m = pattern.search(link)
        if m:
            return m.group(1)
    return "name:" + (row.get("상품명") or "")


# ---------------------------------------------------------------------------
# 카테고리 분류 — 위에서부터 순서대로 검사, 먼저 매칭되는 하나만 사용
# (상품 하나는 정확히 한 카테고리). 순서가 중요하다: 예) "마그네슘&L-테아닌"은
# 미네랄보다 수면·스트레스가 먼저 잡혀야 하고, "숙취해소제 (플러스, 에이, 브이)"는
# 다이어트의 "브이"보다 숙취가 먼저 잡혀야 한다.
# 2026-11-11: 8/12~11/10 전체 데이터에서 "기타"로 빠지던 상품 약 110개를 보고 보강.
# ---------------------------------------------------------------------------
CATEGORY_RULES = [
    ("숙취해소", ["숙취"]),
    ("눈건강", ["루테인", "지아잔틴", "눈건강", "눈 건강"]),
    ("간건강", ["밀크씨슬", "실리마린", "헛개", "간건강"]),
    ("여성건강", ["질유산균", "여성건강", "이소플라본", "우먼", "이노시톨", "감마리놀렌산",
              "월경", "페민", "엽산", "맘스"]),
    ("남성건강", ["전립선", "마카", "남성건강", "쏘팔메토"]),
    ("수면·스트레스", ["멜라토닌", "테아닌", "수면", "꿀잠", "굿슬립", "스트레스",
                  "아쉬아간다", "기분전환", "마그랩", "멜라메이트", "코자아"]),
    ("홍삼", ["홍삼", "흑삼", "정관장", "한뿌리"]),
    ("멀티비타민", ["멀티비타민", "종합비타민", "오쏘몰", "트루바이타민", "올인원 멀티"]),
    ("다이어트", ["다이어트", "슬림", "컷팅", "맥스컷", "디톡스", "체지방", "가르시니아",
              "브이라인", "브이캔디", "브이 캔디", "브이트리티", "브이펌킨", "펌킨티", "하비",
              "버닝", "칼로 ", "칼로스탑", "홀드잇", "콜레올로지", "크롬", "시트르산",
              "클렌즈", "데이톡", "비니거", "급찐급빠", "grn", "효소 리셋", "파비플로라",
              "펌킨"]),
    ("유산균", ["유산균", "프로바이오틱스", "바이오틱스", "락토핏"]),
    ("효소", ["효소", "카무트"]),
    ("오메가3", ["오메가3", "오메가-3", "알티지오메가", "rTG"]),
    ("콜라겐", ["콜라겐"]),
    ("관절·뼈", ["관절", "글루코사민", "콘드로이친", "뼈건강", "MSM", "보스웰리아"]),
    ("이너뷰티", ["글루타치온", "PDRN", "멜라닌", "멜라케어", "미백", "화이트닝",
              "히알루론산", "레티놀", "뮤신", "피부", "이너닷", "글로우", "비오틴",
              "판토텐산", "맥주효모"]),
    ("단백질·식단", ["닭가슴살", "단백질", "프로틴", "식단", "단백이", "한끼통살"]),
    ("야채·그린", ["야채", "케일", "양배추", "그린즈", "샐러드", "헬시그린", "녹즙"]),
    ("장건강", ["식이섬유", "화이바", "프리바이오틱스", "변비", "푸룬", "대장"]),
    ("에너지·피로", ["에너지", "활력", "활기력", "자양강장", "박카스", "벤포", "비타맥스",
                "피로", "아르기닌"]),
    ("혈당·혈행", ["혈당", "혈압", "혈행", "커큐민", "바나바"]),
    ("미네랄", ["마그네슘", "아연", "셀레늄", "칼마디", "철분", "칼슘", "미네랄"]),
    ("면역", ["면역", "이뮨", "프로폴리스"]),
    ("비타민", ["비타민", "아세로라", "칼시페롤", "배러크런치"]),
]
CATEGORY_ORDER = [name for name, _ in CATEGORY_RULES] + ["기타"]


def classify(name: str) -> str:
    upper = (name or "").upper()
    for label, keywords in CATEGORY_RULES:
        for kw in keywords:
            if kw.upper() in upper:
                return label
    return "기타"


# ---------------------------------------------------------------------------
# 브랜드 정규화 — 채널마다 표기가 달라(정관장(LuX), 종근당건강, 칼로(Kalo) ...)
# 같은 브랜드가 다른 브랜드로 보이지 않게 맞춘다. 다이소는 브랜드 컬럼이 비어 있어
# 상품명 앞부분에서 추출한다.
# ---------------------------------------------------------------------------
BRAND_ALIASES = {
    "정관장(LuX)": "정관장",
    "종근당건강": "종근당",
    "칼로(Kalo)": "칼로",
    "씨제이웰케어": "CJ웰케어",
    "CJ": "CJ웰케어",
    "동국": "동국제약",
    "동화": "동화약품",
    "GNM자연의품격": "GNM",
    "보령약국": "보령",
}
# 다이소 상품명에서 바로 찾을 수 있는 브랜드(다른 채널 브랜드 컬럼 값과 함께 사용)
EXTRA_BRANDS = ["휴럼", "동국제약", "대웅제약", "동화약품", "닥터블릿", "안국약품", "비비랩",
                "자연관", "종근당", "고려은단", "일양약품", "경남제약", "보령", "센트룸",
                "뉴트리원", "정관장", "오쏘몰", "그레인온", "닥터린", "셀트리온"]


def normalize_brand(brand: str) -> str:
    brand = (brand or "").strip()
    return BRAND_ALIASES.get(brand, brand)


def strip_tags(name: str) -> str:
    return re.sub(r"[\[\(][^\]\)]*[\]\)]", " ", name or "").strip()


def brand_of(site_id: str, row: dict, known_brands: set) -> str:
    brand = normalize_brand(row.get("브랜드") or "")
    if brand:
        return brand
    name = row.get("상품명") or ""
    # [보령약국 X Pantio] 처럼 브랜드가 대괄호 안에 있는 경우
    m = re.search(r"\[([^\]]+?)\s+X\s+[^\]]+\]", name)
    if m:
        return normalize_brand(m.group(1).strip())
    plain = strip_tags(name)
    # 알려진 브랜드가 상품명 앞쪽에 있으면 그걸 사용 (긴 이름부터 매칭)
    for b in sorted(known_brands, key=len, reverse=True):
        if b and plain.startswith(b):
            return normalize_brand(b)
    first = plain.split()[0] if plain.split() else ""
    return normalize_brand(first)


# ---------------------------------------------------------------------------
# 판촉 방식 태그 — 상품명 문구로 판정. 한 상품에 여러 태그가 붙을 수 있다.
# ---------------------------------------------------------------------------
PROMO_RULES = [
    ("증정·덤", re.compile(r"증정|증량|추가|\d+\s*\+\s*\d+\s*(포|정|입|병|구미|캡슐|일|개|환)|\(\+\s*\d|\+\s*\d+\s*(포|정|입|병|구미|캡슐|일|개)")),
    ("1+1·2+1", re.compile(r"(?<![\d])[12]\s*\+\s*1(?![\d])")),
    ("채널 단독·기획전", re.compile(r"단독|올영픽|OY단독|단독기획")),
    ("셀럽·인플루언서 PICK", re.compile(r"PICK|(?<!올영)(?<!올영 )픽(?![업])", re.IGNORECASE)),
    ("캐릭터·굿즈", re.compile(r"키링|띠부|콜라보|산리오|시나모롤|폼폼푸린|마이멜로디|뽀로로|틴케이스|마그넷|감자숭이|키캡|미니포스터|보냉백|안대")),
    ("선물 포장", re.compile(r"선물포장|쇼핑백|기프트|선물세트|선물 \S*에디션|선물하기")),
    ("특가·할인", re.compile(r"특가|할인|세일|가격혁명|파격")),
    ("기획세트·골라담기", re.compile(r"기획|세트|골라담기|택\s*1|패키지|더블")),
    ("신제품", re.compile(r"\bNEW\b|신제품|신상", re.IGNORECASE)),
]
PROMO_ORDER = [name for name, _ in PROMO_RULES]


def promo_tags(name: str) -> list[str]:
    name = name or ""
    tags = [label for label, rx in PROMO_RULES if rx.search(name)]
    # 1+1·2+1은 증정·덤의 특수형 — 둘 다 걸리면 1+1만 남긴다
    if "1+1·2+1" in tags and "증정·덤" in tags and not re.search(r"증정|증량|추가", name):
        tags.remove("증정·덤")
    return tags
