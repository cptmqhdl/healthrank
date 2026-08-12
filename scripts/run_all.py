"""3개 사이트 크롤러를 순서대로 실행하는 통합 스크립트.

하나의 사이트가 실패해도(사이트 구조 변경, 접속 차단 등) 나머지 사이트는 계속
진행한다. 실행 결과는 data/logs/YYYY-MM-DD.log 에 사이트별 성공/실패, 수집 개수,
오류 메시지를 남긴다.
"""

import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
LOG_DIR = BASE_DIR / "data" / "logs"

CRAWLERS = [
    ("카카오선물하기", "crawl_kakao_gift.py"),
    ("다이소몰", "crawl_daiso.py"),
    ("올리브영", "crawl_oliveyoung.py"),
]


def run_one(site: str, script_name: str) -> dict:
    script_path = SCRIPTS_DIR / script_name
    result = {"site": site, "script": script_name}
    try:
        proc = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        result["stdout"] = proc.stdout
        result["stderr"] = proc.stderr
        result["ok"] = proc.returncode == 0
    except Exception as e:
        result["stdout"] = ""
        result["stderr"] = str(e)
        result["ok"] = False
    return result


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    log_path = LOG_DIR / f"{today}.log"

    lines = [f"===== 실행 시각: {datetime.now().isoformat(timespec='seconds')} ====="]
    any_fail = False

    for site, script_name in CRAWLERS:
        print(f"[{site}] 실행 중...")
        result = run_one(site, script_name)
        status = "성공" if result["ok"] else "실패"
        if not result["ok"]:
            any_fail = True

        lines.append(f"\n--- {site} ({script_name}): {status} ---")
        if result["stdout"]:
            lines.append(result["stdout"].strip())
        if result["stderr"]:
            lines.append("[오류 출력]\n" + result["stderr"].strip())

        print(f"[{site}] {status}")

    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n로그 저장 완료: {log_path}")

    if any_fail:
        print("일부 사이트 수집에 실패했습니다. 로그 파일을 확인하세요.")
    else:
        print("모든 사이트 수집 완료.")


if __name__ == "__main__":
    main()
