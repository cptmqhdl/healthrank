from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=UA, locale="ko-KR")
    page = context.new_page()
    page.goto("https://www.daisomall.co.kr/ds/rank/new", timeout=20000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    # 랭킹 페이지 자체의 카테고리 필터 중 "식품" 클릭 (전역 gnb 말고 랭킹 안의 필터)
    try:
        page.get_by_role("button", name="식품", exact=True).click(timeout=5000)
    except Exception as e:
        print("button 시도 실패:", e)
        try:
            page.get_by_text("식품", exact=True).last.click(timeout=5000)
        except Exception as e2:
            print("text 시도도 실패:", e2)

    page.wait_for_timeout(3000)
    text = page.inner_text("body")
    print("클릭 후 본문 일부:", text[:1200].replace("\n", " | "))
    print()

    cards = page.locator("a[href*='/pd/']")
    print("상품 링크 개수:", cards.count())
    for i in range(min(6, cards.count())):
        parent = cards.nth(i).locator("xpath=ancestor::li[1]")
        try:
            print("-" * 40, i)
            print(repr(parent.inner_text()))
        except Exception as e:
            print("부모 li 못찾음:", e)

    browser.close()
