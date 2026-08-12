from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=UA, locale="ko-KR", viewport={"width": 1400, "height": 1000})
    page = context.new_page()
    page.goto("https://www.oliveyoung.co.kr/store/main/getBestList.do", timeout=20000, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    # 사이트가 쓰는 JS 함수(moveCategoryShop)를 DOM 클릭 없이 직접 호출
    tab = page.get_by_text("건강식품", exact=True).first
    onclick_js = tab.evaluate("el => el.getAttribute('href')")
    print("href 속성:", onclick_js)

    try:
        page.evaluate("common.link.moveCategoryShop('10000020001', 'Drawer', {})")
        print("moveCategoryShop 직접 호출 성공")
    except Exception as e:
        print("직접 호출 실패:", e)

    page.wait_for_timeout(3000)
    print("현재 URL:", page.url)

    cards = page.locator("div.prd_info")
    print("prd_info 개수:", cards.count())
    for i in range(min(5, cards.count())):
        print("-" * 40, i)
        print(repr(cards.nth(i).inner_text()))

    browser.close()
