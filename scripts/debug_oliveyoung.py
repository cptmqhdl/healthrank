from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=UA, locale="ko-KR")
    page = context.new_page()
    url = "https://www.oliveyoung.co.kr/store/main/getBestList.do?dispCatNo=10000020001"
    page.goto(url, timeout=20000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    text = page.inner_text("body")
    print("본문 일부:", text[:800].replace("\n", " | "))
    print()

    cards = page.locator("div.prd_info")
    print("prd_info 개수:", cards.count())
    for i in range(min(5, cards.count())):
        print("-" * 40, i)
        print(repr(cards.nth(i).inner_text()))

    browser.close()
