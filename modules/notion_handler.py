# modules/notion_handler.py
"""
Notion API를 사용하여 데이터베이스를 관리하는 모듈입니다.
- 페이지 생성, 중복 확인, 오래된 항목 삭제, 마크다운 파싱 등을 담당합니다.
"""

import requests
import json
import datetime
import re
import markdown2
from bs4 import BeautifulSoup

# 다른 모듈 및 설정 파일에서 필요한 요소들을 가져옵니다.
# 이제 Notion API 토큰과 두 개의 데이터베이스 ID를 모두 임포트합니다.
from config import NOTION_API_TOKEN, CVE_DATABASE_ID, BOANISSUE_DATABASE_ID
from .utils import send_slack_message, filter_bmp_characters
from .tistory_handler import post_to_tistory

def parse_markdown_to_notion_blocks(markdown_text):
    """
    입력된 마크다운 형식의 텍스트를 Notion 페이지에 적합한 블록 객체 리스트로 변환합니다.
    헤딩, 목록, 인용, 코드 블록 등을 인식하며, 각 블록 내 텍스트는 2000자 제한에 맞춰 분할됩니다.
    """
    blocks = []
    if not markdown_text or not markdown_text.strip():
        blocks.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": "상세 내용이 제공되지 않았습니다."}}]}
        })
        return blocks

    current_paragraph_lines = []
    max_text_length = 2000

    def create_rich_text_array(text_content):
        return [{"type": "text", "text": {"content": text_content}}]

    def split_text_and_create_blocks(block_type, text_content, block_specific_data=None):
        generated_blocks = []
        if text_content is None: text_content = ""

        # Notion 텍스트 제한(2000자)에 맞춰 분할
        while True:
            part = text_content[:max_text_length]
            text_content = text_content[max_text_length:]

            block_content_data = {"rich_text": create_rich_text_array(part)}

            if block_type == "code" and block_specific_data:
                block_content_data["language"] = block_specific_data.get("language", "plaintext")

            generated_blocks.append({"object": "block", "type": block_type, block_type: block_content_data})

            if not text_content: break
        return generated_blocks

    def flush_paragraph_buffer():
        if current_paragraph_lines:
            paragraph_text = "\n".join(current_paragraph_lines).strip()
            if paragraph_text:
                blocks.extend(split_text_and_create_blocks("paragraph", paragraph_text))
            current_paragraph_lines.clear()

    lines = markdown_text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        if line.startswith("### "):
            flush_paragraph_buffer()
            blocks.extend(split_text_and_create_blocks("heading_3", line[4:]))
        elif line.startswith("## "):
            flush_paragraph_buffer()
            blocks.extend(split_text_and_create_blocks("heading_2", line[3:]))
        elif line.startswith("# "):
            flush_paragraph_buffer()
            blocks.extend(split_text_and_create_blocks("heading_1", line[2:]))
        elif line.startswith("- ") or line.startswith("* "):
            flush_paragraph_buffer()
            blocks.extend(split_text_and_create_blocks("bulleted_list_item", line[2:]))
        elif re.match(r"^\d+\.\s", line):
            flush_paragraph_buffer()
            content = re.sub(r"^\d+\.\s", "", line)
            blocks.extend(split_text_and_create_blocks("numbered_list_item", content))
        elif line.startswith("> "):
            flush_paragraph_buffer()
            quote_lines = [line[2:]]
            while i + 1 < len(lines) and lines[i+1].rstrip().startswith("> "):
                i += 1
                quote_lines.append(lines[i].rstrip()[2:])
            blocks.extend(split_text_and_create_blocks("quote", "\n".join(quote_lines)))
        elif line.startswith("```"):
            flush_paragraph_buffer()
            language = line[3:].strip().lower() or "plaintext"
            code_block_lines = []
            i += 1
            while i < len(lines) and not lines[i].rstrip() == "```":
                code_block_lines.append(lines[i])
                i += 1
            code_content = "\n".join(code_block_lines)
            blocks.extend(split_text_and_create_blocks("code", code_content, {"language": language}))
        elif not line.strip():
            flush_paragraph_buffer()
        else:
            current_paragraph_lines.append(line)
        i += 1

    flush_paragraph_buffer()

    if not blocks:
        blocks.append({
            "object": "block", "type": "paragraph",
            "paragraph": {"rich_text": [{"type": "text", "text": {"content": "처리할 수 있는 상세 내용이 없습니다."}}]}
        })
    return blocks


def create_notion_page(title, content, url, date, category_, details, DATABASE_ID):
    """
    주어진 정보를 바탕으로 Notion 데이터베이스에 새 페이지를 생성하고 Tistory에 포스팅합니다.
    DATABASE_ID 매개변수를 추가하여 대상 데이터베이스를 유연하게 지정할 수 있습니다.
    """
    try:
        today = datetime.datetime.now()
        post_date_obj = datetime.datetime.strptime(date, '%Y-%m-%d')
        # 90일이 지난 오래된 뉴스는 건너뜁니다.
        if post_date_obj < (today - datetime.timedelta(days=90)):
            print(f"[SKIP] '{title}'은(는) 90일 이전의 항목이므로 추가하지 않습니다.")
            return
    except ValueError as e:
        print(f"[ERROR] 날짜 형식 오류: {date} - {e}")
        send_slack_message(f"[ERROR] Notion 페이지 생성 중 날짜 형식 오류: {title} - {date} ({e})")
        return

    headers = {
        "Authorization": f"Bearer {NOTION_API_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    # Notion 속성의 텍스트 길이는 2000자로 제한됩니다.
    content_for_property = content[:1997] + '...' if len(content) > 2000 else content

    # `details` (마크다운 텍스트)를 Notion 블록 리스트로 변환
    all_children_blocks = parse_markdown_to_notion_blocks(details)
    
    # Notion API는 한 번에 최대 100개의 블록만 추가할 수 있습니다.
    # 초기 페이지 생성 요청 시에는 맨 첫 100개의 블록만 전송합니다.
    initial_children = all_children_blocks[:100]
    remaining_children = all_children_blocks[100:]

    data = {
        "parent": {"database_id": DATABASE_ID}, # 매개변수로 받은 DATABASE_ID 사용
        "properties": {
            "title": {"title": [{"text": {"content": title}}]},
            "content": {"rich_text": [{"text": {"content": content_for_property}}]},
            "url": {"url": url},
            "date": {"date": {"start": date}},
            "category": {"select": {"name": category_}}
        },
        "children": initial_children # 초기 100개 블록만 전송
    }

    try:
        response = requests.post("https://api.notion.com/v1/pages", headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            page_data = response.json()
            page_id = page_data.get("id")
            print(f"✅ Notion 페이지가 성공적으로 생성되었습니다: {title} (ID: {page_id})")
            
            # --- 나머지 블록 추가 ---
            # 페이지가 생성된 후 나머지 블록들을 추가합니다.
            if remaining_children and page_id:
                print(f"남은 {len(remaining_children)}개의 블록을 추가합니다...")
                block_append_url = f"https://api.notion.com/v1/blocks/{page_id}/children"
                
                # 나머지 블록들을 100개씩 분할하여 추가 요청
                for i in range(0, len(remaining_children), 100):
                    batch = remaining_children[i:i + 100]
                    append_payload = {"children": batch}
                    try:
                        append_response = requests.patch(block_append_url, headers=headers, json=append_payload, timeout=20)
                        if append_response.status_code == 200:
                            print(f"  - {min(i + 100, len(all_children_blocks))}/{len(all_children_blocks)} 블록 추가 완료.")
                        else:
                            error_message = f"Notion 블록 추가 에러 ({page_id}): {append_response.status_code} - {append_response.text}"
                            print(f"❌ {error_message}")
                            send_slack_message(f"[ERROR] {error_message}")
                            break # 오류 발생 시 더 이상 블록 추가 중단
                    except requests.exceptions.RequestException as e:
                        network_error_message = f"Notion 블록 추가 중 네트워크 에러 ({page_id}): {e}"
                        print(f"❌ {network_error_message}")
                        send_slack_message(f"[ERROR] {network_error_message}")
                        break
                print("블록 추가 작업 완료.")
            
            # --- Tistory 포스팅을 위한 본문 준비 (HTML 형식으로 변경) ---
            html_for_tistory = ""
            if isinstance(details, str) and details.strip():
                try:
                    # 마크다운을 HTML로 변환합니다.
                    html_for_tistory = markdown2.markdown(details, extras=["fenced-code-blocks", "tables", "strike"])
                    
                    if not html_for_tistory.strip():
                            html_for_tistory = f"<h2>{title}</h2><p>본문 내용이 없습니다.</p>"

                except Exception as e_conv:
                    print(f"DEBUG: 마크다운 HTML 변환 중 오류: {e_conv}. 기본 HTML을 사용합니다.")
                    html_for_tistory = f"<h2>{title}</h2><p>본문 내용 자동 생성 중 오류가 발생했습니다.</p>"
            else:
                html_for_tistory = f"<h2>{title}</h2><p>상세 내용이 제공되지 않았습니다.</p>"
            
            
            # 티스토리 포스팅을 위해 BMP 이외의 문자 필터링
            filtered_html_for_tistory = filter_bmp_characters(html_for_tistory)
            tags_for_tistory = str(category_)
            url_for_tistory = str(url)
            
            # Notion 데이터베이스 ID에 따라 Tistory 카테고리 설정
            if DATABASE_ID == CVE_DATABASE_ID:
                category_name_for_tistory = "CVE"
            elif DATABASE_ID == BOANISSUE_DATABASE_ID:
                category_name_for_tistory = "보안이슈"
            else:
                category_name_for_tistory = "기타" # 기본값

            # Tistory 포스팅 함수 호출 (이제 filtered_html_for_tistory 변수에는 HTML 코드가 담겨 있습니다)
            success = post_to_tistory(title, filtered_html_for_tistory, tags_for_tistory, category_name_for_tistory, url_for_tistory)
            
            if success:
                print("✅ Tistory 포스팅 성공!")
            else:
                print("❌ Tistory 포스팅 실패.")
        else:
            # Notion API 오류 처리
            error_message = f"노션 페이지 생성 에러: {title} - {response.status_code} - {response.text}"
            print(error_message)
            send_slack_message(f"[ERROR] {error_message}")

    except requests.exceptions.RequestException as e:
        network_error_message = f"노션 페이지 생성 중 네트워크 에러: {title} - {e}"
        print(network_error_message)
        send_slack_message(f"[ERROR] {network_error_message}")
    except Exception as e:
        unknown_error_message = f"노션 페이지 생성 중 알 수 없는 에러: {title} - {e}"
        print(unknown_error_message)
        send_slack_message(f"[ERROR] {unknown_error_message}")

def Duplicate_check(url_to_check, DATABASE_ID):
    """
    주어진 URL이 Notion 데이터베이스에 이미 존재하는지 확인합니다.
    DATABASE_ID 매개변수를 추가하여 대상 데이터베이스를 유연하게 지정할 수 있습니다.
    """
    endpoint = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query" # 매개변수로 받은 DATABASE_ID 사용
    headers = {
        "Authorization": f"Bearer {NOTION_API_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    query_payload = {
        "filter": {
            "property": "url",
            "url": { "equals": url_to_check.strip() }
        }
    }
    try:
        response = requests.post(endpoint, headers=headers, json=query_payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        return 1 if data.get("results") else 0
    except requests.exceptions.RequestException as e:
        print(f"Notion 중복 확인 API 요청 오류: {e}")
        send_slack_message(f"[ERROR] Notion 중복 확인 API 요청 오류: {e}")
        return -1 # 오류 발생 시 -1 반환
    except Exception as e:
        print(f"Notion 중복 확인 중 알 수 없는 오류: {e}")
        send_slack_message(f"[ERROR] Notion 중복 확인 중 알 수 없는 오류: {e}")
        return -1

def delete_old_entries(DATABASE_ID):
    """
    Notion 데이터베이스에서 90일 이상 지난 오래된 항목들을 찾아 보관(archive) 처리합니다.
    DATABASE_ID 매개변수를 추가하여 대상 데이터베이스를 유연하게 지정할 수 있습니다.
    """
    endpoint = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query" # 매개변수로 받은 DATABASE_ID 사용
    headers = {
        "Authorization": f"Bearer {NOTION_API_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }
    threshold_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=90)
    
    pages_to_archive = []
    has_more = True
    start_cursor = None

    print(f"90일 이전 (기준일: {threshold_date.strftime('%Y-%m-%d')}) 항목 삭제(보관) 작업 시작...")

    while has_more:
        query_payload = {
            "filter": {
                "property": "date",
                "date": {"before": threshold_date.isoformat()}
            },
            "page_size": 100
        }
        if start_cursor:
            query_payload["start_cursor"] = start_cursor
        
        try:
            response = requests.post(endpoint, headers=headers, json=query_payload, timeout=20)
            response.raise_for_status()
            data = response.json()
            
            pages_to_archive.extend([page["id"] for page in data.get("results", [])])
            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] 오래된 항목 조회 실패: {e}")
            send_slack_message(f"[ERROR] 오래된 항목 조회 실패: {e}")
            return # 더 이상 진행하지 않고 함수 종료
    
    if not pages_to_archive:
        print("삭제(보관)할 오래된 항목이 없습니다.")
        return

    print(f"총 {len(pages_to_archive)}개의 오래된 항목을 찾았습니다. 보관 처리를 진행합니다.")
    archived_count = 0
    for page_id in pages_to_archive:
        patch_endpoint = f"https://api.notion.com/v1/pages/{page_id}"
        archive_payload = {"archived": True}
        try:
            patch_response = requests.patch(patch_endpoint, headers=headers, json=archive_payload, timeout=10)
            if patch_response.status_code == 200:
                print(f"   - 항목 보관 완료: {page_id}")
                archived_count += 1
            else:
                err_text = patch_response.text
                print(f"   - [ERROR] 항목 보관 실패 ({page_id}): {patch_response.status_code} - {err_text}")
                send_slack_message(f"[ERROR] 항목 보관 실패 ({page_id}): {patch_response.status_code} - {err_text}")
        except requests.exceptions.RequestException as e:
            print(f"   - [ERROR] 항목 보관 요청 중 네트워크 오류 ({page_id}): {e}")
            send_slack_message(f"[ERROR] 항목 보관 요청 중 네트워크 오류 ({page_id}): {e}")
        
    print(f"오래된 항목 삭제(보관) 작업 완료. 총 {archived_count}개 항목 보관됨.")
    if archived_count > 0:
        send_slack_message(f"[INFO] 오래된 항목 삭제(보관) 작업 완료. 총 {archived_count}개 항목 보관됨.")


def get_recent_entries(DATABASE_ID):
    """
    Notion 데이터베이스에서 최근 7일 이내의 항목들을 조회하고 내용을 결합하여 반환합니다.
    '날짜' 속성을 기준으로 필터링합니다.
    """
    endpoint = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_API_TOKEN}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28"
    }

    # 현재로부터 7일 전 날짜 계산
    seven_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
    
    all_pages_combined_content = [] # 모든 페이지의 내용을 담을 리스트
    has_more = True
    start_cursor = None

    print(f"Notion DB (ID: {DATABASE_ID})에서 최근 7일 이내 (기준일: {seven_days_ago.strftime('%Y-%m-%d')}) 항목 조회 시작...")

    while has_more:
        query_payload = {
            "filter": {
                # Notion DB의 '날짜' 속성 이름에 맞게 변경 (property 이름을 date로 가정)
                "property": "date", 
                "date": {"on_or_after": seven_days_ago.isoformat()}
            },
            "sorts": [
                {
                    "property": "date", 
                    "direction": "descending"
                }
            ],
            "page_size": 100
        }
        if start_cursor:
            query_payload["start_cursor"] = start_cursor
        
        try:
            response = requests.post(endpoint, headers=headers, json=query_payload, timeout=20)
            response.raise_for_status()
            data = response.json()
            
            for page in data.get("results", []):
                # Notion 페이지에서 원하는 내용 추출
                title_prop = page.get("properties", {}).get("title", {}).get("title", [])
                title_text = title_prop[0].get("plain_text") if title_prop else "제목 없음"
                
                content_prop = page.get("properties", {}).get("content", {}) # Notion DB의 'content' 속성 이름
                content_text = ""
                if content_prop and content_prop.get("type") == "rich_text":
                    rich_text = content_prop.get("rich_text", [])
                    content_text = "".join([t.get("plain_text") for t in rich_text])
                
                url_prop = page.get("properties", {}).get("url", {})
                url_text = url_prop.get("url") if url_prop else "URL 없음"

                # 페이지의 제목, 요약 내용, URL 등을 결합하여 하나의 문자열로 만듭니다.
                # Gemini가 분석하기 좋은 형태로 정보를 제공합니다.
                full_page_content = f"제목: {title_text}\nURL: {url_text}\n요약: {content_text}\n"
                all_pages_combined_content.append(full_page_content)

            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Notion 최근 항목 조회 실패: {e}")
            send_slack_message(f"[ERROR] Notion 최근 항목 조회 실패: {e}")
            return None # 오류 발생 시 None 반환
    
    if not all_pages_combined_content:
        print("최근 7일간의 Notion 항목이 없습니다.")
        return None

    print(f"총 {len(all_pages_combined_content)}개의 Notion 항목을 찾았습니다.")
    # 모든 페이지의 내용을 하나의 큰 텍스트로 결합하여 반환
    return "\n---\n".join(all_pages_combined_content)