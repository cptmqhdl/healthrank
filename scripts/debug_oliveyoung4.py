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

    text = page.inner_text("body")
    print("본문 일부:", text[:1500].replace("\n", " | "))
    print()

    # 정렬(판매순/인기순 등) 옵션 찾기
    for kw in ["판매순", "인기순", "리뷰순", "정렬"]:
        try:
            el = page.get_by_text(kw, exact=False).first
            print(f"'{kw}' 발견 여부:", el.count() if hasattr(el, 'count') else True)
        except Exception:
            pass

    for sel in ["div.prd_info", "ul.cate_prd_list li", "li.flag", "div.prd-info", "ul#Contents li"]:
        c = page.locator(sel).count()
        print(f"selector '{sel}':", c)
        if c > 0:
            print("  첫 항목:", page.locator(sel).first.inner_text()[:200].replace("\n", " | "))

    browser.close()
