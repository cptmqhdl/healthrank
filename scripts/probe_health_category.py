"""건강기능식품 카테고리 탭을 클릭한 뒤 실제 상품 목록 구조(HTML)를 확인하는 진단 스크립트."""

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def probe(page, name, url, category_text, item_selector_guess):
    print("=" * 70)
    print(name)
    page.goto(url, timeout=20000, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    try:
        page.get_by_text(category_text, exact=True).first.click(timeout=8000)
        page.wait_for_timeout(2500)
        print(f"[{category_text}] 탭 클릭 성공")
    except Exception as e:
        print(f"[{category_text}] 탭 클릭 실패:", repr(e))

    text = page.inner_text("body")
    print("클릭 후 본문 일부:", text[:500].replace("\n", " | "))

    # 후보 상품 카드 컨테이너 개수 확인
    for sel in item_selector_guess:
        try:
            count = page.locator(sel).count()
            print(f"selector '{sel}' 개수:", count)
            if count > 0:
                print("   첫 항목 outerHTML(700자):", page.locator(sel).first.evaluate("el => el.outerHTML").replace("\n", " ")[:700])
        except Exception as e:
            print(f"selector '{sel}' 오류:", repr(e))


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=UA, locale="ko-KR")
    page = context.new_page()

    probe(
        page, "올리브영 베스트 - 건강식품",
        "https://www.oliveyoung.co.kr/store/main/getBestList.do",
        "건강식품",
        ["li.thumb-box", "div.prd_info", "ul#gdasList li", "li[data-ref-goodsno]", "div.cate_prd_list li"]
    )

    probe(
        page, "카카오 선물하기 랭킹 - 건강",
        "https://gift.kakao.com/ranking",
        "건강",
        ["li[class*=item]", "div[class*=item_prod]", "a[href*='/product/']", "li a[href*='product_id']"]
    )

    probe(
        page, "다이소몰 랭킹 - 건강식품",
        "https://www.daisomall.co.kr/ds/rank/new",
        "건강식품",
        ["li.item", "div.goods-unit", "a[href*='/pd/']", "li[class*=prod]"]
    )

    browser.close()
