"""세 사이트가 실제 브라우저로는 접근/렌더링이 되는지 확인하는 진단 스크립트.
크롤러 본제작 전에, 어느 사이트가 가장 다루기 쉬운지 확인하기 위한 용도."""

from playwright.sync_api import sync_playwright

SITES = [
    ("다이소몰 랭킹", "https://www.daisomall.co.kr/ds/rank/new"),
    ("카카오 선물하기 랭킹", "https://gift.kakao.com/ranking"),
    ("올리브영 베스트", "https://www.oliveyoung.co.kr/store/main/getBestList.do"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        locale="ko-KR",
    )
    page = context.new_page()

    for name, url in SITES:
        print("=" * 60)
        print(name, url)
        try:
            resp = page.goto(url, timeout=20000, wait_until="domcontentloaded")
            print("status:", resp.status if resp else None)
            page.wait_for_timeout(3000)
            text = page.inner_text("body")
            snippet = text[:600].replace("\n", " | ")
            print("body snippet:", snippet)
            print("body length:", len(text))
        except Exception as e:
            print("ERROR:", repr(e))

    browser.close()
