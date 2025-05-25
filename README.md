-----

# 보안 뉴스 자동화 어그리게이터 (Security News Aggregator)

이 프로젝트는 다양한 온라인 보안 뉴스 소스(웹사이트, RSS 피드)를 주기적으로 크롤링하고, AI를 통해 콘텐츠를 가공하여 Notion 데이터베이스에 저장하고 Tistory 블로그에 자동으로 포스팅하는 자동화 시스템입니다. 모든 작업 상태 및 오류는 Slack으로 알림을 받습니다.

## 주요 기능

  - 📰 **다중 소스 크롤링**: 보안뉴스, 데일리시큐, KRCERT, NCSC 등 여러 보안 관련 사이트의 최신 정보를 수집합니다.
  - 🤖 **AI 콘텐츠 가공**: Google Gemini API를 사용하여 수집된 뉴스의 본문을 요약하고, 핵심 기술에 대한 상세 분석을 생성합니다.
  - 📝 **Notion DB 자동화**: 처리된 데이터를 Notion 데이터베이스에 자동으로 페이지를 생성하여 체계적으로 관리하고, 오래된 데이터는 주기적으로 삭제(보관)합니다.
  - 🚀 **Tistory 자동 포스팅**: Notion에 저장된 콘텐츠를 기반으로 Tistory 블로그에 자동으로 글을 발행합니다.
  - 📢 **Slack 알림**: 작업 시작, 완료, 오류 발생 등 주요 이벤트에 대한 알림을 실시간으로 Slack에 전송하여 모니터링을 용이하게 합니다.
  - ⏰ **스케줄링**: 전체 프로세스가 매시간 정각에 자동으로 실행되도록 설정되어 있습니다.

## 기술 스택

  - **언어**: Python 3.8+
  - **크롤링**: Selenium, BeautifulSoup4, Requests
  - **AI 모델**: Google Gemini API (`google-generative-ai`)
  - **API 연동**: Notion API, Slack API, Tistory (via Selenium)
  - **스케줄링**: Schedule
  - **기타**: `webdriver-manager`, `markdown2`

## 프로젝트 구조

```
security_news_aggregator/
│
├── main.py                 # 프로그램의 시작점, 스케줄러 실행
├── config.py               # API 키, 데이터베이스 ID 등 모든 설정값 관리
├── requirements.txt        # 프로젝트에 필요한 라이브러리 목록
│
└── modules/
    ├── __init__.py           # 이 디렉토리를 파이썬 패키지로 인식시킴
    ├── crawlers.py           # 모든 웹사이트 및 RSS 크롤링 함수
    ├── gemini_handler.py     # Gemini API 호출 관련 함수 (요약, 상세 분석)
    ├── notion_handler.py     # Notion API 관련 함수 (페이지 생성, 중복 확인, 삭제)
    ├── tistory_handler.py    # Tistory 포스팅 자동화 함수
    └── utils.py              # 기타 유틸리티 함수 (슬랙 알림, 날짜 변환 등)
```

## 설치 및 설정

### 1\. 프로젝트 복제

```bash
git clone <repository-url>
cd security_news_aggregator
```

### 2\. 가상 환경 생성 및 활성화 (권장)

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3\. 필요 라이브러리 설치

```bash
pip install -r requirements.txt
```

### 4\. 환경 설정

> **⚠️ 중요:** 이 프로젝트를 실행하려면 `config.py` 파일에 개인 API 키와 ID를 설정해야 합니다.

`config.py` 파일을 열고 아래 변수들의 값을 자신의 정보로 수정하세요.

  - `GEMINI_API_KEY`: Google AI Studio에서 발급받은 Gemini API 키
  - `NOTION_API_TOKEN`: Notion 통합(Integration)에서 발급받은 내부 통합 토큰
  - `DATABASE_ID`: Notion 데이터베이스의 ID (데이터베이스 URL에서 확인 가능)
  - `SLACK_WEBHOOK_URL`: Slack 앱에서 생성한 Incoming Webhook URL
  - `TISTORY_EMAIL`: Tistory 로그인에 사용하는 카카오 이메일
  - `TISTORY_PASSWORD`: Tistory 로그인 비밀번호
  - `TISTORY_BLOG_NAME`: 글을 발행할 Tistory 블로그의 이름 (예: `my-blog`)

## 실행 방법

모든 설정이 완료된 후, 터미널에서 아래 명령어를 실행하여 프로젝트를 시작합니다.

```bash
python main.py
```

스크립트는 시작 시 모든 작업을 한 번 즉시 실행한 후, 매시간 정각에 다시 실행되는 스케줄러를 활성화합니다.

### 스케줄러 비활성화

만약 스케줄링 없이 일회성으로만 실행하고 싶다면, 환경 변수 `RUN_SCHEDULER`를 `false`로 설정하고 실행하세요.

```bash
# macOS / Linux
RUN_SCHEDULER=false python main.py

# Windows (Command Prompt)
set RUN_SCHEDULER=false
python main.py
```
