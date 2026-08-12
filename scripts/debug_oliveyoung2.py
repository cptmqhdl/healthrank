from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=UA, locale="ko-KR", viewport={"width": 1400, "height": 1000})
    page = context.new_page()
    page.goto("https://www.oliveyoung.co.kr/store/main/getBestList.do", timeout=20000, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    tab = page.get_by_text("건강식품", exact=True).first
    tab.scroll_into_view_if_needed(timeout=5000)
    page.wait_for_timeout(500)
    tab.click(force=True, timeout=5000)
    page.wait_for_timeout(3000)

    cards = page.locator("div.prd_info")
    print("건강식품 클릭 후 prd_info 개수:", cards.count())
    for i in range(min(5, cards.count())):
        print("-" * 40, i)
        print(repr(cards.nth(i).inner_text()))

    browser.close()
