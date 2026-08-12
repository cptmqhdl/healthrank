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

    heading = page.get_by_text("건강식품의 BEST만 모아봤어요", exact=False).first
    info = heading.evaluate("""
        el => {
            let sec = el.closest('section') || el.closest('div');
            // 부모를 몇 단계 올라가며 li/ul 구조 찾기
            let cur = el;
            let path = [];
            for (let i=0;i<6;i++) {
                cur = cur.parentElement;
                if (!cur) break;
                path.push(cur.tagName + '.' + cur.className);
            }
            return path.join(' > ');
        }
    """)
    print("상위 요소 경로:", info)

    container = heading.locator("xpath=following::ul[1]")
    print("following ul 존재:", container.count())
    if container.count() > 0:
        print("class:", container.first.evaluate("el => el.className"))
        items = container.first.locator("> li")
        print("li 개수:", items.count())
        for i in range(min(6, items.count())):
            print("-" * 30, i)
            print(repr(items.nth(i).inner_text()))

    browser.close()
