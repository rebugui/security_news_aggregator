# config.py
"""
이 파일은 프로젝트의 모든 설정값을 중앙에서 관리합니다.
API 키, 토큰, 데이터베이스 ID, 웹훅 URL 등을 포함합니다.
"""

import ssl

# --- 전역 설정값 ---

# SSL 인증서 검증 비활성화 (특정 환경에서 SSL 오류 발생 시 임시 조치)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Google Gemini API 키
GEMINI_API_KEY = "GEMINI_API_KEY"  # 실제 API 키로 교체해야 합니다.

# Notion API 설정
NOTION_API_TOKEN = "NOTION_API_TOKEN" # Notion 통합 토큰
DATABASE_ID = "DATABASE_ID" # Notion 데이터베이스 ID

# Slack Webhook URL (알림용)
SLACK_WEBHOOK_URL = "https://SLACK_WEBHOOK_URL" # 실제 Slack Webhook URL로 교체해야 합니다. 

# Tistory 로그인 정보
TISTORY_EMAIL = "TISTORY_EMAIL@kakao.com"
TISTORY_PASSWORD = "TISTORY_PASSWORD"
TISTORY_BLOG_NAME = "TISTORY_BLOG_NAME"
