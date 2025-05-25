# modules/crawlers.py
"""
다양한 보안 뉴스 웹사이트 및 RSS 피드를 크롤링하는 모듈입니다.
- NCSC 보안공지 (Selenium)
- KRCERT 보안공지 (RSS)
- 보안뉴스 (RSS)
- 데일리시큐 (RSS)
"""

import time
import urllib.request
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup

# Selenium 관련 라이브러리
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# 다른 모듈에서 필요한 함수 및 설정값 임포트
from config import ssl_context
from .utils import date_re, send_slack_message
from .notion_handler import Duplicate_check, create_notion_page
from .gemini_handler import summarize_text, details_text


def crawl_ncsc_page():
    """
    NCSC(국가사이버안보센터) 웹사이트의 '보안공지' 게시판에서 최신 게시글을 크롤링합니다.
    """
    source_name = "NCSC 보안공지"
    driver = None
    print(f"--- {source_name} 크롤링 시작 ---")
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            print(f"[{source_name}-ERROR] ChromeDriver 설정 중 오류: {e}")
            send_slack_message(f"[ERROR] {source_name} - ChromeDriver 설정 오류: {e}")
            return

        target_url = "https://www.ncsc.go.kr:4018"
        driver.get(target_url)
        print(f"[{source_name}-INFO] NCSC 웹사이트 접속 시도: {target_url}")

        driver.execute_script("goSubMenuPage('020000','020200')")
        print(f"[{source_name}-INFO] 보안공지 메뉴로 이동 실행 (goSubMenuPage('020000','020200'))")

        time.sleep(5)

        soup = BeautifulSoup(driver.page_source, 'html.parser')

        board_list_table = soup.find('table', class_='board_list')
        if not board_list_table:
            message = f"[{source_name}-WARN] 게시판 목록 테이블('table.board_list')을 찾을 수 없습니다."
            print(message)
            send_slack_message(f"[WARNING] {message} (URL: {driver.current_url})")
            return

        tr_tags = board_list_table.find('tbody').find_all('tr')
        if not tr_tags:
            print(f"[{source_name}-INFO] 게시판에 게시글이 없습니다.")
            return

        print(f"[{source_name}-INFO] {len(tr_tags)}개의 게시글 행을 찾았습니다. 각 항목 처리 시작...")

        items_processed = 0
        for tr_tag in tr_tags:
            items_processed +=1
            td_tags = tr_tag.find_all('td')
            title_cell = td_tags[1]
            a_tag = title_cell.find('a')

            if a_tag and a_tag.has_attr('onclick'):
                article_title = a_tag.text.strip()

                onclick_script = a_tag['onclick']
                print(f"  [{source_name}-INFO] '{article_title}' 상세 페이지 이동 시도 (onclick: {onclick_script})")
                driver.execute_script(onclick_script)
                time.sleep(3)

                article_url = driver.current_url

                posting_date_str = td_tags[2].text.strip()
                posting_date = date_re(posting_date_str)

                if not posting_date:
                    print(f"  [{source_name}-SKIP] 날짜 변환 실패 항목: {article_title} (원본 날짜: {posting_date_str})")
                    driver.back()
                    time.sleep(2)
                    continue

                duplicate_status = Duplicate_check(article_url)
                if duplicate_status == 0:
                    print(f"  [{source_name}-PROCESSING] 새 항목: {article_title}")
                    
                    # NCSC는 상세 본문 크롤링이 복잡하므로, 제목 기반으로 내용을 생성합니다.
                    # 만약 실제 본문을 분석하고 싶다면, 아래 주석 처리된 로직을 활성화하고
                    # NCSC 웹사이트 구조에 맞게 본문 내용 선택자를 수정해야 합니다.
                    page_text_content = article_title 
                    
                    # summary_for_notion = summarize_text(page_text_content)
                    # details_for_notion = details_text(page_text_content)
                    
                    # 임시로 제목을 요약 및 상세 내용으로 사용
                    summary_for_notion = f"NCSC 보안공지: {article_title}"
                    details_for_notion = f"## 🔍 뉴스 요약\n\nNCSC(국가사이버안보센터)에서 '{article_title}'에 대한 보안공지를 발표했습니다.\n\n## 💡 핵심 포인트\n\n- 자세한 내용은 원문 링크를 참조하시기 바랍니다."

                    create_notion_page(article_title, summary_for_notion, article_url, posting_date, "NCSC", details_for_notion)

                elif duplicate_status == 1:
                    print(f"  [{source_name}-SKIP] 중복된 항목: {article_title}")
                else:
                    print(f"  [{source_name}-SKIP] 중복 확인 중 오류 발생 항목: {article_title}")

                print(f"  [{source_name}-INFO] 목록 페이지로 복귀 중...")
                driver.back()
                time.sleep(2)
            else:
                print(f"  [{source_name}-WARN] {items_processed}번째 행에서 제목 링크(a_tag) 또는 onclick 속성을 찾을 수 없습니다.")

    except Exception as e:
        print(f"[{source_name}-ERROR] 크롤링 중 오류 발생: {e}")
        current_url_info = ""
        if driver and hasattr(driver, 'current_url') and driver.current_url:
            current_url_info = f" (현재 URL: {driver.current_url})"
        send_slack_message(f"[ERROR] {source_name} 크롤링 중 오류 발생{current_url_info}: {e}")
    finally:
        if driver:
            driver.quit()
            print(f"[{source_name}-INFO] WebDriver 종료됨.")


def securityNotice_crawling():
    """KRCERT(한국인터넷진흥원) 보안 공지 RSS 피드를 크롤링합니다."""
    source_name = "KRCERT 보안공지"
    url = 'http://knvd.krcert.or.kr/rss/securityNotice.do'
    try:
        print(f"--- {source_name} 크롤링 시작 ({url}) ---")
        with urllib.request.urlopen(url, context=ssl_context, timeout=15) as response:
            xml_data = response.read().decode('utf-8')

        root = ET.fromstring(xml_data)
        channel = root.find('channel')
        if channel is None:
            print(f"{source_name} RSS 피드에서 'channel' 태그를 찾을 수 없습니다.")
            return

        items_processed = 0
        for item_elem in channel.findall('item'):
            items_processed +=1
            title = item_elem.findtext('title', default='제목 없음').strip()
            link_url = item_elem.findtext('link', default='').strip()
            original_content = item_elem.findtext('description', default='내용 없음').strip()
            pub_date_str = item_elem.findtext('pubDate', default='').strip()
            category_ = "KRCERT"

            if not link_url:
                print(f"[{source_name}-SKIP] URL 없는 항목: {title}")
                continue

            posting_date = date_re(pub_date_str)
            if not posting_date:
                print(f"[{source_name}-SKIP] 날짜 변환 실패 항목: {title} (원본 날짜: {pub_date_str})")
                continue

            duplicate_status = Duplicate_check(link_url)
            if duplicate_status == 0:
                print(f"[{source_name}-PROCESSING] 새 항목: {title}")
                summarized_content = summarize_text(original_content)
                details_content = details_text(original_content)

                if "실패" in summarized_content or "실패" in details_content:
                    send_slack_message(f"[WARN] {source_name} '{title}' 처리 중 Gemini API 실패. "
                                       f"요약: {summarized_content}, 상세: {details_content}")

                create_notion_page(title, summarized_content, link_url, posting_date, category_, details_content)
            elif duplicate_status == 1:
                print(f"[{source_name}-SKIP] 중복된 항목: {title}")
            else:
                 print(f"[{source_name}-SKIP] 중복 확인 중 오류 발생 항목: {title}")

    except urllib.error.URLError as e:
        print(f"{source_name} RSS URL({url}) 열기 실패: {e}")
        send_slack_message(f"[ERROR] {source_name} RSS URL 열기 실패: {e}")
    except ET.ParseError as e:
        print(f"{source_name} RSS XML 파싱 실패: {e}")
        send_slack_message(f"[ERROR] {source_name} RSS XML 파싱 실패: {e}")
    except Exception as e:
        print(f"{source_name} 크롤링 중 알 수 없는 오류 발생: {e}")
        send_slack_message(f"[ERROR] {source_name} 크롤링 중 알 수 없는 오류 발생: {e}")


def boanNews_crawling():
    """보안뉴스 RSS 피드를 크롤링합니다. pubDate와 dc:date 태그를 모두 확인합니다."""
    source_name = "보안뉴스"
    namespaces = {'dc': 'http://purl.org/dc/elements/1.1/'}

    try:
        urls = [
            'http://www.boannews.com/media/news_rss.xml?skind=5',
            'http://www.boannews.com/media/news_rss.xml?skind=6',
            'http://www.boannews.com/media/news_rss.xml?mkind=1'
        ]
        print(f"--- {source_name} 크롤링 시작 ---")
        for rss_url in urls:
            print(f"  - {rss_url} 처리 중...")
            try:
                response = requests.get(rss_url, timeout=15)
                response.raise_for_status()
                response.encoding = response.apparent_encoding
                root = ET.fromstring(response.text)
                channel = root.find('channel')

                if channel is None:
                    print(f"  [{source_name}-WARN] RSS ({rss_url})에서 'channel' 태그를 찾을 수 없습니다.")
                    continue

                for item_elem in channel.findall('item'):
                    title = item_elem.findtext('title', default='제목 없음').strip()
                    link_url = item_elem.findtext('link', default='').strip()
                    original_content = item_elem.findtext('description', default='내용 없음').strip()
                    category_ = "보안뉴스"

                    pub_date_str = item_elem.findtext('pubDate', default='').strip()
                    if not pub_date_str:
                        dc_date_element = item_elem.find('dc:date', namespaces)
                        if dc_date_element is None:
                            dc_date_element = item_elem.find('{http://purl.org/dc/elements/1.1/}date')
                        if dc_date_element is not None and dc_date_element.text:
                            pub_date_str = dc_date_element.text.strip()

                    if not link_url:
                        print(f"  [{source_name}-SKIP] URL 없는 항목: {title}")
                        continue
                    
                    posting_date = date_re(pub_date_str)
                    if not posting_date:
                        print(f"  [{source_name}-SKIP] 날짜 변환 실패 항목: {title} (원본 날짜: '{pub_date_str}')")
                        continue

                    if rss_url.endswith('mkind=1') and "[긴급]" not in title:
                        continue

                    duplicate_status = Duplicate_check(link_url)
                    if duplicate_status == 0:
                        print(f"  [{source_name}-PROCESSING] 새 항목: {title}")
                        summarized_content = summarize_text(original_content)
                        details_content = details_text(original_content)
                        if "실패" in summarized_content or "실패" in details_content:
                            send_slack_message(f"[WARN] {source_name} '{title}' 처리 중 Gemini API 실패. "
                                               f"요약: {summarized_content}, 상세: {details_content}")
                        create_notion_page(title, summarized_content, link_url, posting_date, category_, details_content)
                    elif duplicate_status == 1:
                        print(f"  [{source_name}-SKIP] 중복된 항목: {title}")
                    else:
                        print(f"  [{source_name}-SKIP] 중복 확인 중 오류 발생 항목: {title}")

            except requests.exceptions.RequestException as e:
                print(f"  [{source_name}-ERROR] RSS ({rss_url}) 요청 실패: {e}")
                send_slack_message(f"[ERROR] {source_name} RSS ({rss_url}) 요청 실패: {e}")
                continue
            except ET.ParseError as e:
                print(f"  [{source_name}-ERROR] RSS ({rss_url}) XML 파싱 실패: {e}")
                send_slack_message(f"[ERROR] {source_name} RSS ({rss_url}) XML 파싱 실패: {e}")
                continue
    except Exception as e:
        print(f"{source_name} 크롤링 중 알 수 없는 오류 발생: {e}")
        send_slack_message(f"[ERROR] {source_name} 크롤링 중 알 수 없는 오류 발생: {e}")


def dailysecu_crawling():
    """데일리시큐 RSS 피드를 크롤링합니다."""
    source_name = "데일리시큐"
    url = 'https://www.dailysecu.com/rss/S1N2.xml'
    try:
        print(f"--- {source_name} 크롤링 시작 ({url}) ---")
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            root = ET.fromstring(response.text)
            channel = root.find('channel')
            if channel is None:
                print(f"{source_name} RSS ({url})에서 'channel' 태그를 찾을 수 없습니다.")
                return

            for item_elem in channel.findall('item'):
                title = item_elem.findtext('title', default='제목 없음').strip()
                link_url = item_elem.findtext('link', default='').strip()
                original_content = item_elem.findtext('description', default='내용 없음').strip()
                category_ = "데일리시큐"
                
                pub_date_str = item_elem.findtext('pubDate', default='').strip()
                if not pub_date_str:
                    dc_date_elem = item_elem.find('{http://purl.org/dc/elements/1.1/}date')
                    if dc_date_elem is not None and dc_date_elem.text:
                        pub_date_str = dc_date_elem.text.strip()

                if not link_url:
                    print(f"[{source_name}-SKIP] URL 없는 항목: {title}")
                    continue

                posting_date = date_re(pub_date_str)
                if not posting_date:
                    print(f"[{source_name}-SKIP] 날짜 변환 실패 항목: {title} (원본 날짜: {pub_date_str})")
                    continue

                duplicate_status = Duplicate_check(link_url)
                if duplicate_status == 0:
                    print(f"[{source_name}-PROCESSING] 새 항목: {title}")
                    summarized_content = summarize_text(original_content)
                    details_content = details_text(original_content)
                    if "실패" in summarized_content or "실패" in details_content:
                        send_slack_message(f"[WARN] {source_name} '{title}' 처리 중 Gemini API 실패. "
                                           f"요약: {summarized_content}, 상세: {details_content}")
                    create_notion_page(title, summarized_content, link_url, posting_date, category_, details_content)
                elif duplicate_status == 1:
                    print(f"[{source_name}-SKIP] 중복된 항목: {title}")
                else:
                    print(f"[{source_name}-SKIP] 중복 확인 중 오류 발생 항목: {title}")

        except requests.exceptions.RequestException as e:
            print(f"{source_name} RSS ({url}) 요청 실패: {e}")
            send_slack_message(f"[ERROR] {source_name} RSS ({url}) 요청 실패: {e}")
        except ET.ParseError as e:
            print(f"{source_name} RSS ({url}) XML 파싱 실패: {e}")
            send_slack_message(f"[ERROR] {source_name} RSS ({url}) XML 파싱 실패: {e}")
    except Exception as e:
        print(f"{source_name} 크롤링 중 알 수 없는 오류 발생: {e}")
        send_slack_message(f"[ERROR] {source_name} 크롤링 중 알 수 없는 오류 발생: {e}")