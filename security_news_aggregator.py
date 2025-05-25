# main.py
"""
이 스크립트는 전체 보안 뉴스 크롤링 및 처리 작업을 실행하고 스케줄링합니다.
이 파일을 실행하여 모든 작업을 시작합니다.
"""

import time
import datetime
import schedule
import os

# 설정 및 모듈 함수 임포트
from config import GEMINI_API_KEY, NOTION_API_TOKEN, DATABASE_ID, SLACK_WEBHOOK_URL
from modules.crawlers import boanNews_crawling, dailysecu_crawling, securityNotice_crawling, crawl_ncsc_page
from modules.notion_handler import delete_old_entries
from modules.utils import send_slack_message

def start():
    """
    정의된 모든 크롤링 작업을 순차적으로 실행하고,
    오래된 Notion 항목 삭제 작업을 수행합니다.
    """
    overall_start_time = time.time()
    current_time_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print(f"[{current_time_str}] 스케쥴링 작업을 시작합니다.")
    send_slack_message(f"[{current_time_str}] 보안뉴스 크롤링 및 Notion 업데이트 작업을 시작합니다.")

    crawling_tasks = [
        ("보안뉴스", boanNews_crawling),
        ("데일리시큐", dailysecu_crawling),
        ("KRCERT 보안공지", securityNotice_crawling),
        ("NCSC 보안공지", crawl_ncsc_page)
    ]

    for task_name, task_function in crawling_tasks:
        task_start_time = time.time()
        try:
            print(f"--- {task_name} 크롤링 시작 ---")
            task_function()
            task_duration = time.time() - task_start_time
            print(f"--- {task_name} 크롤링 완료 (소요 시간: {task_duration:.2f}초) ---")
        except Exception as e:
            task_duration = time.time() - task_start_time
            error_msg = f"{task_name} 크롤링 전체 실행 중 오류 발생 (소요 시간: {task_duration:.2f}초): {e}"
            print(f"[CRITICAL] {error_msg}")
            send_slack_message(f"[CRITICAL ERROR] {error_msg}")
        time.sleep(1)

    delete_task_start_time = time.time()
    try:
        print("--- 오래된 항목 삭제 작업 시작 ---")
        delete_old_entries()
        delete_task_duration = time.time() - delete_task_start_time
        print(f"--- 오래된 항목 삭제 작업 완료 (소요 시간: {delete_task_duration:.2f}초) ---")
    except Exception as e:
        delete_task_duration = time.time() - delete_task_start_time
        error_msg = f"오래된 항목 삭제 작업 중 오류 발생 (소요 시간: {delete_task_duration:.2f}초): {e}"
        print(f"[CRITICAL] {error_msg}")
        send_slack_message(f"[CRITICAL ERROR] {error_msg}")

    overall_duration = time.time() - overall_start_time
    current_time_str_end = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    completion_message = (f"[{current_time_str_end}] 모든 작업 완료. "
                          f"(총 소요 시간: {overall_duration:.2f}초)")
    print(completion_message)
    send_slack_message(completion_message)

if __name__ == "__main__":
    # 설정값이 비어 있는지 확인
    if "YOUR_" in GEMINI_API_KEY or "YOUR_" in NOTION_API_TOKEN or "YOUR_" in DATABASE_ID or "YOUR_" in SLACK_WEBHOOK_URL:
        print("주의: config.py 파일의 API 키, 토큰, ID, URL 등이 실제 값으로 설정되지 않았습니다.")
        print("스크립트 실행을 중단합니다.")
    else:
        # 프로그램 시작 시 1회 즉시 실행
        start()

        # 환경 변수에 따라 스케줄러 실행 여부 결정
        run_scheduler_env = os.environ.get("RUN_SCHEDULER", "true").lower()
        if run_scheduler_env == "true":
            schedule.every(1).hours.at(":00").do(start)

            current_time_for_log = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{current_time_for_log}] 스케줄러가 설정되었습니다. 매시간 정각에 작업이 실행됩니다.")
            send_slack_message(f"[{current_time_for_log}] 스케줄러 시작됨. 매시간 정각 실행 예정.")

            try:
                while True:
                    schedule.run_pending()
                    time.sleep(30)
            except KeyboardInterrupt:
                print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 사용자에 의해 스케줄러가 종료되었습니다.")
                send_slack_message(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 스케줄러 수동 종료됨.")
            except Exception as e:
                error_message = f"메인 스케줄링 루프 실행 중 치명적 오류 발생: {e}"
                print(error_message)
                send_slack_message(f"[CRITICAL ERROR] {error_message}")
        else:
            current_time_for_log = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f"[{current_time_for_log}] 스케줄러 실행이 비활성화되었습니다 (RUN_SCHEDULER 환경 변수: {run_scheduler_env}).")
