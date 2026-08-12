from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=UA, locale="ko-KR")
    page = context.new_page()
    page.goto("https://gift.kakao.com/ranking", timeout=20000, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    page.get_by_text("건강", exact=True).first.click()
    page.wait_for_timeout(1500)
    page.get_by_text("건강식품·영양제", exact=True).first.click()
    page.wait_for_timeout(2000)

    cards = page.locator("div.unit_prd")
    for i in range(5):
        print("=" * 50, "card", i)
        print(repr(cards.nth(i).inner_text()))
    browser.close()
