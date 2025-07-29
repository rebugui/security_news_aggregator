# modules/utils.py
"""
프로젝트 전반에서 사용되는 유틸리티 함수들을 모아놓은 모듈입니다.
- 슬랙 메시지 전송
- BMP 문자 필터링
- 날짜 형식 변환
"""

import requests
import datetime
import re
from config import SLACK_WEBHOOK_URL

def filter_bmp_characters(s):
    """
    주어진 문자열에서 BMP(Basic Multilingual Plane) 외부의 문자를 제거합니다.
    """
    if not isinstance(s, str):
        return s  # 문자열이 아니면 그대로 반환
    return "".join(c for c in s if ord(c) <= 0xFFFF)

def send_slack_message(message):
    """
    주어진 메시지를 Slack으로 전송합니다.
    """
    payload = {"text": message}
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()  # HTTP 오류 발생 시 예외를 발생시킴
        print("슬랙 메시지 전송 성공!")
    except requests.exceptions.RequestException as e:
        print(f"슬랙 메시지 전송 실패: {e}")

def date_re(date_string):
    """
    다양한 형식의 날짜 문자열을 'YYYY-MM-DD' 형식으로 변환합니다.
    """
    if not date_string: return None

    formats_to_try = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y.%m.%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d",
    ]
    for fmt in formats_to_try:
        try:
            # datetime 모듈의 datetime 클래스 사용 (datetime.datetime)
            date_object = datetime.datetime.strptime(date_string.strip(), fmt)
            return date_object.strftime('%Y-%m-%d')
        except ValueError:
            continue
        # strptime이 실패했을 때 fromisoformat으로 추가 시도 (특히 Z나 오프셋 처리)
        try:
            if 'T' in date_string and ('Z' in date_string or '+' in date_string[date_string.find('T'):] or '-' in date_string[date_string.find('T'):]):
                # 'Z'를 +00:00으로 대체하여 fromisoformat이 인식하도록 합니다.
                iso_date_string = date_string.strip().replace('Z', '+00:00')
                date_object = datetime.datetime.fromisoformat(iso_date_string)
                return date_object.strftime('%Y-%m-%d')
        except ValueError:
            continue
        
    print(f"알 수 없는 날짜 형식 또는 변환 실패: '{date_string}'")
    return None
