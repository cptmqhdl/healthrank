from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(user_agent=UA, locale="ko-KR", viewport={"width": 1400, "height": 1000})
    page = context.new_page()
    url = "https://www.oliveyoung.co.kr/store/display/getCategoryShop.do?dispCatNo=10000020001&gateCd=Drawer&"
    page.goto(url, timeout=20000, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    best = page.locator("div.ct-best")
    print("ct-best 개수:", best.count())
    html = best.first.evaluate("el => el.outerHTML")
    print(html[:3000])

    browser.close()
