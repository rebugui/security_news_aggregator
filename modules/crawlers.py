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
import json
from datetime import datetime, timedelta
import urllib.parse # <-- 이 부분도 추가되어 있어야 합니다.

# Selenium 관련 라이브러리
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# 다른 모듈에서 필요한 함수 및 설정값 임포트
from config import ssl_context, CVE_DATABASE_ID, BOANISSUE_DATABASE_ID
from .utils import date_re, send_slack_message
from .notion_handler import Duplicate_check, create_notion_page, get_recent_entries # get_recent_entries 추가
from .gemini_handler import summarize_text, details_text, CVE_details_text, extract_and_explain_keywords, generate_weekly_tech_blog_post

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

                duplicate_status = Duplicate_check(article_url,BOANISSUE_DATABASE_ID)
                if duplicate_status == 0:
                    print(f"  [{source_name}-PROCESSING] 새 항목: {article_title}")

                    # --- NCSC 상세 페이지 본문 크롤링 로직 시작 ---
                    page_detail_soup = BeautifulSoup(driver.page_source, 'html.parser')
                    article_content_element = page_detail_soup.find('div', class_='board_view_con')

                    page_text_content = ""
                    
                    if article_content_element:
                        # 1. 'editor_view' 내부의 텍스트를 우선 시도
                        editor_view_element = article_content_element.find('div', class_='editor_view')
                        if editor_view_element:
                            extracted_text_from_editor = editor_view_element.get_text(separator='\n', strip=True)
                            if extracted_text_from_editor:
                                page_text_content = extracted_text_from_editor
                                print(f"  [{source_name}-INFO] 'editor_view'에서 본문 내용 추출 성공. 길이: {len(page_text_content)}자")
                            else:
                                print(f"  [{source_name}-INFO] 'editor_view'는 비어 있습니다. 이미지/첨부파일 정보 확인.")
                        else:
                            print(f"  [{source_name}-INFO] 'editor_view'를 찾을 수 없습니다. 이미지/첨부파일 정보 확인.")

                        # 2. 이미지의 title 속성에서 텍스트 추출 시도 (page_text_content가 비어있을 경우 또는 추가 정보로)
                        img_element = article_content_element.find('img')
                        if img_element and img_element.get('title'):
                            img_title = urllib.parse.unquote(img_element['title']).strip()
                            if img_title.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')): # 파일명 확장자 제거
                                img_title = img_title.rsplit('.', 1)[0]
                            
                            if not page_text_content.strip(): # 텍스트 본문이 비어있다면 이미지 title로 대체
                                page_text_content = f"NCSC 보안공지: {article_title} (핵심 내용: {img_title})"
                                print(f"  [{source_name}-INFO] 이미지 제목({img_title})으로 본문 내용 구성.")
                            elif img_title not in page_text_content: # 기존 내용에 이미지 title이 없다면 추가 정보로 병합
                                page_text_content += f"\n\n핵심 이미지: {img_title}"
                                print(f"  [{source_name}-INFO] 기존 본문에 이미지 제목({img_title}) 추가.")

                        # 3. 첨부파일 정보에서 텍스트 추가 시도 (page_text_content가 비어있을 경우 또는 추가 정보로)
                        attachment_file_box = page_detail_soup.find('div', class_='board_view_file')
                        if attachment_file_box:
                            attachment_link = attachment_file_box.find('a', onclick=lambda x: x and 'fn_downFile' in x)
                            if attachment_link:
                                attachment_text = attachment_link.get_text(strip=True)
                                if attachment_text.strip():
                                    if not page_text_content.strip(): # 본문 내용이 아직 비어있다면 첨부파일 제목으로 대체
                                        page_text_content = f"NCSC 보안공지: {article_title} (첨부파일: {attachment_text})"
                                        print(f"  [{source_name}-INFO] 첨부파일({attachment_text})로 본문 내용 구성.")
                                    elif attachment_text not in page_text_content: # 기존 내용에 첨부파일 정보가 없다면 추가
                                        page_text_content += f"\n\n관련 파일: {attachment_text}"
                                        print(f"  [{source_name}-INFO] 기존 본문에 첨부파일({attachment_text}) 정보 추가.")
                    else:
                        # board_view_con 요소 자체를 찾지 못한 경우
                        print(f"  [{source_name}-WARN] 상세 페이지에서 본문 요소('div.board_view_con')를 찾을 수 없습니다. 제목으로 대체합니다.")
                        send_slack_message(f"[WARNING] {source_name} '{article_title}' 본문 크롤링 실패. URL: {article_url}")
                        page_text_content = article_title # 요소 찾기 실패 시 제목으로 대체
                    
                    # 최종적으로 page_text_content가 여전히 비어 있다면, 원래의 임시 로직 적용
                    if not page_text_content.strip():
                        print(f"  [{source_name}-WARN] 최종 본문 텍스트가 비어 있어 초기 임시 로직을 사용합니다.")
                        summary_for_notion = f"NCSC 보안공지: {article_title}"
                        details_for_notion = f"## 🔍 뉴스 요약\n\nNCSC(국가사이버안보센터)에서 '{article_title}'에 대한 보안공지를 발표했습니다.\n\n## 💡 핵심 포인트\n\n- 자세한 내용은 원문 링크를 참조하시기 바랍니다."
                    else:
                        # 텍스트가 성공적으로 추출/구성된 경우 Gemini API 호출
                        summarized_content = summarize_text(page_text_content)
                        details_content = details_text(page_text_content)

                        if "실패" in summarized_content or "실패" in details_content:
                            send_slack_message(f"[WARN] {source_name} '{article_title}' 처리 중 Gemini API 실패. "
                                               f"요약: {summarized_content}, 상세: {details_content}")
                        
                        summary_for_notion = summarized_content
                        details_for_notion = details_content

                    # --- NCSC 상세 페이지 본문 크롤링 로직 끝 ---

                    create_notion_page(article_title, summary_for_notion, article_url, posting_date, "NCSC", details_for_notion, BOANISSUE_DATABASE_ID)

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

            duplicate_status = Duplicate_check(link_url,BOANISSUE_DATABASE_ID)
            if duplicate_status == 0:
                print(f"[{source_name}-PROCESSING] 새 항목: {title}")
                summarized_content = summarize_text(original_content)
                details_content = details_text(original_content)

                if "실패" in summarized_content or "실패" in details_content:
                    send_slack_message(f"[WARN] {source_name} '{title}' 처리 중 Gemini API 실패. "
                                       f"요약: {summarized_content}, 상세: {details_content}")

                create_notion_page(title, summarized_content, link_url, posting_date, category_, details_content,BOANISSUE_DATABASE_ID)
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

                    duplicate_status = Duplicate_check(link_url,BOANISSUE_DATABASE_ID)
                    if duplicate_status == 0:
                        print(f"  [{source_name}-PROCESSING] 새 항목: {title}")
                        summarized_content = summarize_text(original_content)
                        details_content = details_text(original_content)
                        if "실패" in summarized_content or "실패" in details_content:
                            send_slack_message(f"[WARN] {source_name} '{title}' 처리 중 Gemini API 실패. "
                                               f"요약: {summarized_content}, 상세: {details_content}")
                        create_notion_page(title, summarized_content, link_url, posting_date, category_, details_content,BOANISSUE_DATABASE_ID)
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

                duplicate_status = Duplicate_check(link_url,BOANISSUE_DATABASE_ID)
                if duplicate_status == 0:
                    print(f"[{source_name}-PROCESSING] 새 항목: {title}")
                    summarized_content = summarize_text(original_content)
                    details_content = details_text(original_content)
                    if "실패" in summarized_content or "실패" in details_content:
                        send_slack_message(f"[WARN] {source_name} '{title}' 처리 중 Gemini API 실패. "
                                           f"요약: {summarized_content}, 상세: {details_content}")
                    create_notion_page(title, summarized_content, link_url, posting_date, category_, details_content,BOANISSUE_DATABASE_ID)
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

def nvd_cve_crawling():
    """NVD API v2.0 JSON 데이터를 크롤링합니다 (최근 90일만)."""
    source_name = "NVD CVE"
    base_url = 'https://services.nvd.nist.gov/rest/json/cves/2.0'

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=10) # NVD API는 최대 120일
    pubStartDate = start_date.strftime("%Y-%m-%dT00:00:00.000")
    pubEndDate = end_date.strftime("%Y-%m-%dT23:59:59.999")

    params = {
        "pubStartDate": pubStartDate,
        "pubEndDate": pubEndDate,
        "resultsPerPage": 2000
    }

    try:
        print(f"--- {source_name} 크롤링 시작 ({base_url}) ---")
        try:
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            vulnerabilities = data.get('vulnerabilities', [])
            for vuln in vulnerabilities:
                cve = vuln.get('cve', {})
                cve_id = cve.get('id', '제목 없음')
                published = cve.get('published', '')
                descriptions = cve.get('descriptions', [])
                description_en = next((desc['value'] for desc in descriptions if desc['lang'] == 'en'), '내용 없음')

                category_ = "CVE"
                link_url = f"https://nvd.nist.gov/vuln/detail/{cve_id}"

                posting_date = date_re(published)

                duplicate_status = Duplicate_check(link_url, CVE_DATABASE_ID)
                if duplicate_status == 0:
                    print(f"[{source_name}-PROCESSING] 새 항목: {cve_id}")
                    # CVE_details_text가 이제 (제목, 본문) 튜플을 반환합니다.
                    generated_cve_title, generated_cve_body = CVE_details_text(description_en)
                    
                    # 요약은 별도로 summarize_text로 만들거나, generated_cve_body에서 일부 발췌
                    summarized_content = summarize_text(description_en) # 원래대로 원문으로 요약

                    if "실패" in generated_cve_title or "실패" in generated_cve_body:
                        send_slack_message(f"[WARN] {source_name} '{cve_id}' 처리 중 Gemini API 실패. "
                                           f"생성 제목: {generated_cve_title}, 생성 본문: {generated_cve_body}")

                    # Notion 페이지 생성 시, Gemini가 생성한 제목과 본문을 사용합니다.
                    create_notion_page(generated_cve_title, summarized_content, link_url, posting_date, category_, generated_cve_body, CVE_DATABASE_ID)
                elif duplicate_status == 1:
                    print(f"[{source_name}-SKIP] 중복된 항목: {cve_id}")
                else:
                    print(f"[{source_name}-SKIP] 중복 확인 중 오류 발생 항목: {cve_id}")

        except requests.exceptions.RequestException as e:
            print(f"{source_name} API 요청 실패: {e}")
            send_slack_message(f"[ERROR] {source_name} API 요청 실패: {e}")
        except json.JSONDecodeError as e:
            print(f"{source_name} JSON 파싱 실패: {e}")
            send_slack_message(f"[ERROR] {source_name} JSON 파싱 실패: {e}")
    except Exception as e:
        print(f"{source_name} 크롤링 중 알 수 없는 오류 발생: {e}")
        send_slack_message(f"[ERROR] {source_name} 크롤링 중 알 수 없는 오류 발생: {e}")


# Week_nvd_cve_crawling 함수 내부 수정:
def Week_nvd_cve_crawling():
    """NVD API v2.0 JSON 데이터를 크롤링하여 최근 7일치 CVE를 하나의 Notion 페이지로 등록합니다."""
    source_name = "NVD CVE 주간 요약" # 이름 변경으로 명확화
    base_url = 'https://services.nvd.nist.gov/rest/json/cves/2.0'

    # 최근 7일 구간 계산
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=7)
    pubStartDate = start_date.strftime("%Y-%m-%dT00:00:00.000")
    pubEndDate = end_date.strftime("%Y-%m-%dT23:59:59.999")

    params = {
        "pubStartDate": pubStartDate,
        "pubEndDate": pubEndDate,
        "resultsPerPage": 2000
    }

    try:
        print(f"--- {source_name} 크롤링 시작 ({base_url}) ---")
        try:
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            vulnerabilities = data.get('vulnerabilities', [])
            all_descriptions_for_summary = []  # 모든 CVE 원문을 요약용으로 모을 리스트

            for vuln in vulnerabilities:
                cve = vuln.get('cve', {})
                cve_id = cve.get('id', '제목 없음')
                descriptions = cve.get('descriptions', [])
                description_en = next((desc['value'] for desc in descriptions if desc['lang'] == 'en'), '내용 없음')
                
                # 주간 요약용 텍스트에 각 CVE ID와 설명을 추가
                all_descriptions_for_summary.append(f"CVE ID: {cve_id}\n설명: {description_en}\n")

            # 모든 CVE 원문을 하나의 텍스트로 결합
            combined_cve_text = "\n---\n".join(all_descriptions_for_summary)

            if all_descriptions_for_summary:
                print(f"총 {len(vulnerabilities)}개의 CVE를 기반으로 블로그 포스트 생성 요청 중...")
                # CVE_details_text 함수를 호출하여 (제목, 본문) 튜플을 받습니다.
                raw_generated_blog_title, generated_blog_body = CVE_details_text(combined_cve_text)
                
                # Notion 속성용 요약은 별도로 생성 (예: 처음 200자)
                page_summary_for_notion_property = "최근 7일간의 주요 CVE를 분석한 상세 보고서입니다."
                if len(generated_blog_body) > 200:
                    page_summary_for_notion_property = generated_blog_body[:197] + "..."

                if "실패" in raw_generated_blog_title or "실패" in generated_blog_body:
                    print(f"[{source_name}-ERROR] Gemini API를 통한 CVE 블로그 포스트 생성 실패: 제목: {raw_generated_blog_title}, 본문: {generated_blog_body}")
                    send_slack_message(f"[ERROR] {source_name} - CVE 블로그 포스트 생성 실패: {raw_generated_blog_title}, {generated_blog_body}")
                    return
                
                # Gemini가 생성한 제목 앞에 기간을 붙입니다.
                generated_blog_title = f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')} {raw_generated_blog_title}"

            else:
                # CVE가 없을 경우에도 기간을 포함한 제목을 생성합니다.
                generated_blog_title = f"{start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')} 주간 CVE 요약 (내용 없음)"
                generated_blog_body = "최근 7일간 새로운 CVE가 발견되지 않았습니다."
                page_summary_for_notion_property = "최근 7일간 새로운 CVE가 없습니다."

            # 7일치 CVE 블로그를 하나의 페이지로 등록
            print(f"[{source_name}] CVE 블로그 포스트를 Notion 페이지로 등록 시작")
            create_notion_page(
                title=generated_blog_title, # 기간이 포함된 제목 사용
                content=page_summary_for_notion_property, # Notion 속성용 요약
                url="https://rebugui.tistory.com", # 고정 URL 또는 적절히 변경
                date=end_date.strftime('%Y-%m-%d'),
                category_="CVE 주간이슈", # 새로운 카테고리 또는 적절히 변경
                details=generated_blog_body, # Gemini가 생성한 전체 블로그 본문
                DATABASE_ID=CVE_DATABASE_ID # CVE 데이터베이스 ID 사용
            )
            print(f"[{source_name}] CVE 블로그 포스트 Notion 페이지 등록 완료.")
            send_slack_message(f"[INFO] {source_name} - '{generated_blog_title}' Notion 페이지 생성 완료.")
        
        except requests.exceptions.RequestException as e:
            print(f"{source_name} API 요청 실패: {e}")
            send_slack_message(f"[ERROR] {source_name} API 요청 실패: {e}")
        except json.JSONDecodeError as e:
            print(f"{source_name} JSON 파싱 실패: {e}")
            send_slack_message(f"[ERROR] {source_name} JSON 파싱 실패: {e}")
    except Exception as e:
        print(f"{source_name} 크롤링 중 알 수 없는 오류 발생: {e}")
        send_slack_message(f"[ERROR] {source_name} 크롤링 중 알 수 없는 오류 발생: {e}")


def generate_weekly_tech_keywords():
    """
    지정된 Notion 데이터베이스에서 최근 7일간의 모든 기술 관련 내용을 가져와
    주요 기술 키워드 10개와 설명을 Gemini API를 통해 생성하고 Notion에 새 페이지로 발행합니다.
    -> 이 함수를 확장하여 블로그 글 형식으로 주간 이슈를 생성합니다.
    """
    source_name = "주간 기술 블로그 포스트 생성"
    print(f"--- {source_name} 작업 시작 (대상 DB: {BOANISSUE_DATABASE_ID}) ---")

    # 1. Notion DB에서 최근 7일간의 모든 항목 내용 가져오기
    # 이 텍스트는 Gemini API의 '주제'이자 '본문'으로 활용됩니다.
    combined_articles_text = get_recent_entries(BOANISSUE_DATABASE_ID)

    if not combined_articles_text:
        print(f"[{source_name}] 최근 7일간의 기술 정보가 없어 블로그 포스트를 생성할 수 없습니다.")
        send_slack_message(f"[INFO] {source_name} - 최근 7일간 기술 정보 없음. 블로그 포스트 생성 건너뜀.")
        return

    # 2. Gemini API를 사용하여 블로그 글 생성
    # combined_articles_text를 {주제}에 해당하는 내용으로 전달합니다.
    print(f"[{source_name}] 수집된 텍스트 ({len(combined_articles_text)}자)로 기술 블로그 포스트 생성 요청 중...")
    
    # generate_weekly_tech_blog_post 함수는 제목과 본문을 튜플로 반환합니다.
    generated_title, generated_body = generate_weekly_tech_blog_post(combined_articles_text)

    if "실패" in generated_title or "실패" in generated_body:
        print(f"[{source_name}-ERROR] Gemini API를 통한 블로그 포스트 생성 실패: 제목: {generated_title}, 본문: {generated_body}")
        send_slack_message(f"[ERROR] {source_name} - 블로그 포스트 생성 실패: {generated_title}, {generated_body}")
        return

    # 3. Notion에 새로운 페이지로 발행
    current_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=6)).strftime('%Y-%m-%d') # 최근 7일이므로 오늘 포함 7일 전

    # generate_weekly_tech_blog_post에서 받은 제목을 그대로 사용
    page_title = generated_title 
    page_summary = "최근 한 주간 주요 보안 및 기술 이슈를 분석하여 생성된 블로그 포스트입니다." # Notio n 속성용 요약
    page_url = "https://rebugui.tistory.com" # 혹은 적절한 기본 URL 설정
    category = "주간이슈" # Notion DB의 카테고리 속성 이름에 맞게 설정

    print(f"[{source_name}] 생성된 블로그 포스트를 Notion 페이지로 발행: '{page_title}'")
    create_notion_page(
        title=page_title,
        content=page_summary, # Notion 속성용 요약 (간략화된 내용)
        url=page_url,
        date=current_date,
        category_=category,
        details=generated_body, # Gemini가 생성한 전체 블로그 본문
        DATABASE_ID=BOANISSUE_DATABASE_ID # 보안이슈를 관리하는 데이터베이스 ID 사용
    )
    send_slack_message(f"[INFO] {source_name} - '{page_title}' Notion 페이지 생성 완료.")
    print(f"--- {source_name} 작업 완료 ---")
