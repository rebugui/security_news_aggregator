# modules/tistory_handler.py


import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoAlertPresentException, UnexpectedAlertPresentException

from config import TISTORY_EMAIL, TISTORY_PASSWORD, TISTORY_BLOG_NAME

def post_to_tistory(title_text, content_text, tags_text, category_name, source_url_text=None):
    print(f"티스토리 자동 포스팅 시작: '{title_text}'")

    chrome_options = Options()
    # 화면을 보면서 디버깅합니다.
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = None
    posting_successful = False

    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        print("WebDriver 시작됨")

        driver.get('https://accounts.kakao.com/login/?continue=https%3A%2F%2Fkauth.kakao.com%2Foauth%2Fauthorize%3Fclient_id%3D3e6ddd834b023f24221217e370daed18%26prompt%3Dselect_account%26redirect_uri%3Dhttps%253A%252F%252Fwww.tistory.com%252Fauth%252Fkakao%252Fredirect%26response_type%3Dcode')
        print(f"카카오 로그인 페이지 접속: {driver.current_url}")

        try:
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, 'loginId')))
            email_input = driver.find_element(By.NAME, 'loginId')
            email_input.send_keys(TISTORY_EMAIL)
            password_input = driver.find_element(By.NAME, 'password')
            password_input.send_keys(TISTORY_PASSWORD)
            print("이메일 및 비밀번호 입력 완료.")

            login_button_selector = "button.btn_g.highlight.submit"
            login_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, login_button_selector))
            )
            driver.execute_script("arguments[0].click();", login_button)
            print("1차 카카오 로그인 버튼 클릭 (JavaScript 실행).")

        except Exception as e:
            print(f"1차 카카오 로그인 과정 중 오류 발생: {e}")
            driver.save_screenshot("debug_screenshot_kakao_login_error.png")
            raise

        try:
            tistory_kakao_login_button_xpath = "//*[contains(text(), '카카오계정으로 로그인')]"
            tistory_login_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, tistory_kakao_login_button_xpath))
            )
            print("중간 티스토리 로그인 페이지 확인. '카카오계정으로 로그인' 버튼 클릭 시도.")
            driver.execute_script("arguments[0].click();", tistory_login_button)
        except TimeoutException:
            print("중간 티스토리 로그인 페이지가 감지되지 않았습니다. 직접 로그인 된 것으로 간주하고 계속 진행합니다.")

        # --- [핵심 수정 1]: 기본 관리 페이지로 먼저 이동 ---
        manage_page_url = f'https://{TISTORY_BLOG_NAME}.tistory.com/manage'
        print(f"기본 관리 페이지로 이동 시도: {manage_page_url}")
        driver.get(manage_page_url)

        print(f"1. 기본 관리 페이지({manage_page_url})로 URL 변경 및 로드 확인 중...")
        WebDriverWait(driver, 20).until(EC.url_contains(f"{TISTORY_BLOG_NAME}.tistory.com/manage")) # /manage 까지는 가는지
        # 페이지 타이틀이나 특정 요소가 있는지 확인하여 로드가 완료되었는지 검증할 수 있습니다.
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "kakaoServiceLogo"))) # 예: 관리 페이지 상단 로고
        print(f"   기본 관리 페이지 로드 확인 완료: {driver.current_url}")

        print("기본 관리 페이지에서 3초 대기...")
        time.sleep(3)
        # -------------------------------------------------

        # --- [핵심 수정 2]: 글쓰기 페이지로 이동 및 안정성 확보 ---
        write_page_url = f'https://{TISTORY_BLOG_NAME}.tistory.com/manage/newpost'
        print(f"글쓰기 페이지로 직접 이동 시도: {write_page_url}")
        driver.get(write_page_url)

       # --- [핵심 수정: 알림창 처리 로직 - 페이지 로드 직후 가장 먼저 실행] ---
        alert_handled_successfully = False
        try:
            print("DEBUG: 글쓰기 페이지 진입. 알림창 즉시 확인 및 처리 시도 (최대 7초 대기)...")
            WebDriverWait(driver, 7).until(EC.alert_is_present())

            alert = driver.switch_to.alert
            alert_text = alert.text
            print(f"DEBUG: 알림 발견! 내용: '{alert_text}'")

            if "저장된 글이 있습니다" in alert_text:
                print("DEBUG: '저장된 글' 알림. alert.dismiss()로 '취소'를 시도합니다.")
                alert.dismiss() # 표준적인 취소 방법
                print("DEBUG: alert.dismiss() 실행 완료.")
            else:
                print(f"WARN: 예상치 못한 다른 알림입니다: '{alert_text}'. '확인' (accept) 처리합니다.")
                alert.accept()

            alert_handled_successfully = True
            time.sleep(0.5) # DOM 안정화를 위한 짧은 대기

        except TimeoutException:
            print("DEBUG: 알림창이 지정된 시간 내에 나타나지 않았습니다 (정상적인 경우).")
            alert_handled_successfully = True
        except NoAlertPresentException:
             print("DEBUG: NoAlertPresentException. 알림창 없음 (정상적인 경우).")
             alert_handled_successfully = True
        except UnexpectedAlertPresentException as uap_inner:
            # 이 블록 안에서 UnexpectedAlertPresentException이 발생하면,
            # WebDriverWait(EC.alert_is_present())가 true를 반환했음에도
            # driver.switch_to.alert 등의 작업 중 다른 alert이 끼어들었거나 매우 특이한 상황.
            print(f"ERROR: 알림 처리 중 다시 UnexpectedAlertPresentException 발생: {uap_inner.alert_text if hasattr(uap_inner, 'alert_text') else 'N/A'}")
            # 이 경우, 일단 현재 떠 있는 알림을 닫는 시도를 한번 더 할 수 있습니다.
            try:
                current_alert = driver.switch_to.alert
                print(f"   (Fallback) 실제 알림 텍스트: {current_alert.text}. Dismiss 시도.")
                current_alert.dismiss()
                time.sleep(1)
                alert_handled_successfully = True # 일단 처리된 것으로 간주하고 로깅
            except Exception as e_double_fault:
                print(f"   (Fallback) 알림 처리 완전 실패: {e_double_fault}")
                raise uap_inner # 원래 오류를 다시 발생시켜 중단
        except Exception as e_alert_handler_other:
             print(f"ERROR: 알림창 처리 중 예상 못한 오류 발생: {e_alert_handler_other}")
             raise e_alert_handler_other # 더 진행하지 않고 오류 발생

        if not alert_handled_successfully: # 이 조건에 걸리면 심각한 문제
            print("CRITICAL: 알림창 처리에 실패했습니다. 스크립트를 중단합니다.")
            # driver.save_screenshot("debug_screenshot_alert_critical_failure.png") # 최종 오류 블록에서 처리
            raise Exception("Alert was not handled successfully on new post page.")
        # --- 알림창 처리 로직 끝 ---


        # 알림창 처리 후, 페이지 URL 및 기본 요소 로드 확인
        print(f"DEBUG: 알림 처리 후 URL 확인 중... 현재 URL: {driver.current_url}")
        WebDriverWait(driver, 15).until(EC.url_contains("/manage/newpost"))
        print(f"   URL 변경 재확인 완료: {driver.current_url}")

        print("DEBUG: 페이지 기본 요소(body) 로드 대기 중...")
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("   페이지 기본 요소 로드 확인 완료.")
        time.sleep(1)

        print("DEBUG: 글쓰기 페이지 제목 입력창 활성화 대기 중...")
        # title_input_element는 알림 처리 후 다시 가져오는 것이 안전합니다.
        title_input_element = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.ID, "post-title-inp"))
        )
        print(f"   글쓰기 페이지 제목 입력창 활성화 확인: {driver.current_url}")


        #1단계: 카테고리 선택
        try:
            # 원하시는 카테고리 이름으로 이 변수 값을 변경하세요.
            category_name_to_select = category_name
            print(f"카테고리 '{category_name_to_select}' 선택 시도...")

            # 카테고리 선택 드롭다운 버튼 클릭
            category_dropdown_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "category-btn"))
            )
            category_dropdown_button.click()
            print("카테고리 메뉴 열기 완료.")

            # [수정] 제공된 HTML 구조에 맞춰 XPath를 수정합니다.
            # role이 'option'인 div 요소 중, 자식 span의 텍스트가 일치하는 것을 찾습니다.
            category_option_xpath = f"//div[@role='option'][span/text()='{category_name_to_select}']"

            print(f"카테고리 옵션({category_option_xpath}) 대기 중...")
            category_option = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, category_option_xpath))
            )
            category_option.click()
            print(f"카테고리 '{category_name_to_select}' 선택 완료.")
            time.sleep(1) # 선택 후 UI가 안정적으로 반영될 때까지 대기
        except Exception as e:
            # 카테고리 선택은 부가 기능으로, 실패하더라도 전체 발행 과정이 중단되지 않도록 합니다.
            print(f"경고: 카테고리('{category_name_to_select}') 선택 중 오류가 발생했습니다. '카테고리 없음'으로 발행될 수 있습니다. 오류: {e}")
            driver.save_screenshot("debug_screenshot_category_error.png")


        # 제목 입력
        title_input_element.send_keys("["+tags_text+"]"+title_text)
        print("제목 입력 완료: ", "["+tags_text+"]"+title_text)

        time.sleep(1)

        try:
            html_content_to_post = content_text

            if source_url_text:
                html_content_to_post += f'<br><p><b>출처:</b> <a href="{source_url_text}" target="_blank" rel="noopener noreferrer">{source_url_text}</a></p>'

            # iframe으로 전환
            WebDriverWait(driver, 20).until(
                EC.frame_to_be_available_and_switch_to_it((By.ID, "editor-tistory_ifr"))
            )
            print("본문 편집 iframe으로 전환 성공. 👍")

            # 에디터의 body 요소를 찾습니다.
            body_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "tinymce"))
            )

            # 1. JavaScript로 HTML 내용을 먼저 주입합니다.
            driver.execute_script("arguments[0].innerHTML = arguments[1];", body_element, html_content_to_post)
            print("본문 HTML 내용 주입 완료.")

            # [핵심 추가] 2. 주입 후, 에디터 본문을 클릭하여 '활성화'하고 '포커스'를 줍니다.
            # 이 과정은 에디터가 변경된 내용을 자신의 '상태'로 인식하게 하는 중요한 역할을 합니다.
            print("에디터 본문 활성화를 위해 클릭 실행...")
            body_element.click()
            time.sleep(1) # 클릭 후 에디터가 반응할 시간을 줍니다.
            print("본문 활성화 완료.")

            # 3. 기본 콘텐츠(iframe 외부)로 돌아오기
            driver.switch_to.default_content()
            print("기본 콘텐츠로 돌아오기 완료.")
        except Exception as e:
            print(f"본문 입력 중 오류 발생: {e} 😥")
            driver.save_screenshot("debug_screenshot_body_input_error.png")
            # 오류 발생 시에도 안전하게 기본 콘텐츠로 돌아오도록 시도합니다.
            try:
                driver.switch_to.default_content()
            except: pass
            raise

        # --- 태그 입력 ---
        try:
            print("태그 입력 시도...")
            tag_input_element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "tagText"))
            )
            # 이전에 입력된 태그가 있다면 지웁니다. (선택 사항)
            # tag_input_element.clear()
            tag_input_element.send_keys(tags_text)
            print(f"태그 입력 완료: {tags_text} 🏷️")
            time.sleep(1) # 입력 후 안정화를 위한 짧은 대기
        except Exception as e:
            # 태그 입력은 부가 기능이므로, 실패해도 포스팅은 계속될 수 있도록 오류 메시지만 출력합니다.
            print(f"태그 입력 중 오류 발생 (ID: tagText). 태그 없이 진행합니다: {e} 😥")
            driver.save_screenshot("debug_screenshot_tag_input_error.png")


        # --- 발행 버튼 클릭 (안정성 강화 최종 버전) ---
        try:
            # 1단계: '발행' 버튼 클릭하여 발행 설정 창 열기
            print("1단계: '발행' 버튼을 눌러 설정 창 열기 시도...")
            publish_layer_open_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "publish-layer-btn"))
            )
            publish_layer_open_button.click()
            print("'발행' 버튼 클릭 완료.")

            # 2단계: 발행 설정 창이 화면에 완전히 나타날 때까지 대기
            # [수정] 제공해주신 HTML을 분석하여 올바른 CSS 선택자('div.editor_layer')로 변경했습니다.
            publish_layer_container_selector = "div.editor_layer"
            print(f"발행 설정 창({publish_layer_container_selector})이 나타날 때까지 대기...")
            WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, publish_layer_container_selector))
            )
            print("발행 설정 창 확인 완료.")

            # [핵심 추가] 3단계: '공개' 옵션 클릭
            # 기본값이 '비공개'로 설정되어 있으므로, '공개' 라디오 버튼(ID: open20)을 명시적으로 클릭합니다.
            print("'공개' 라디오 버튼 클릭 시도 (ID: open20)...")
            public_radio_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "open20")) # HTML에서 확인한 '공개' 라디오 버튼의 ID
            )
            public_radio_button.click()
            print("'공개' 옵션 선택 완료.")
            # 옵션 선택 후, 최종 발행 버튼의 상태(예: 텍스트 변경)가 업데이트될 시간을 줍니다.
            time.sleep(1)

            # 4단계: 설정 창 안의 최종 '발행' 버튼 클릭
            print("최종 '발행' 버튼 클릭 시도 (ID: publish-btn)...")
            final_publish_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "publish-btn"))
            )
            final_publish_button.click()
            print("최종 '발행' 버튼 클릭 완료! 🚀")

            # 5단계: 발행이 완료되고 글쓰기 페이지를 떠날 때까지 대기
            print("게시글 발행 후 페이지 이동 대기 중 (글 목록 페이지로 이동 예상)...")
            WebDriverWait(driver, 30).until(
                EC.url_contains("/manage/posts/")
            )

            print("게시글 발행 성공 확인! 글 목록 페이지로 이동했습니다. 현재 URL:", driver.current_url)
            posting_successful = True
        except Exception as e:
            print(f"발행 과정 중 오류 발생: {e} 😥")
            driver.save_screenshot("debug_screenshot_publish_process_error.png")
            raise

    except Exception as e_global:
        print(f"💥 스크립트 실행 중 예외 발생: {e_global}")
        if driver:
            try:
                current_url_on_error = "N/A"
                page_source_on_error_snippet = "N/A"
                try:
                    current_url_on_error = driver.current_url
                    page_source_on_error_snippet = driver.page_source[:500]
                except: pass
                print(f"  오류 발생 시점 URL: {current_url_on_error}")
                print(f"  오류 발생 시점 페이지 소스 (일부): {page_source_on_error_snippet}")

                final_error_screenshot_name = "debug_screenshot_fatal_error.png"
                driver.save_screenshot(final_error_screenshot_name)
                print(f"함수 실행 중 치명적 오류 발생 시 스크린샷 저장됨: {final_error_screenshot_name}")
            except Exception as screenshot_err:
                print(f"치명적 오류 스크린샷 저장 실패: {screenshot_err}")
    finally:
        if driver:
            driver.quit()
            print("WebDriver 종료됨.")

    return posting_successful