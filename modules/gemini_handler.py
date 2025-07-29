# modules/gemini_handler.py
"""
Google Gemini API를 사용하여 텍스트를 요약하고 상세 분석하는 모듈입니다.
"""

import google.generativeai as genai
from config import GEMINI_API_KEY
from .utils import send_slack_message
import re # <-- 이 줄을 추가해주세요!

def details_text(text):
    """
    입력된 텍스트[본문]를 바탕으로 Gemini API를 사용하여
    정보 보안 기술에 대한 상세 설명을 생성합니다. (상세 분석용 프롬프트 사용)
    """
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash") # 모델명은 최신 버전으로 사용하는 것을 권장합니다.

        prompt = f"""
정보 보안 관련 기술에 대한 상세 설명을 제공하는 블로그 작성 AI입니다.

제시된 **[본문]**에 언급된 보안 관련 기술을 분석하여 자세한 설명을 작성하십시오.

필요 없는 정보는 제거해줘. 작성 시 이모지를 활용해 깔끔하고 구체적으로 정리해줘.

<핵심 참고 사항>

- 기술적 용어나 고유명사같은건 영어 그대로 사용해줘.
- 세부내용에는 최대한 놓치는 정보 없이 자세하게 정리해줘.
- 세부내용에는 최대한 내용 생략 없이 자세하게 정리해줘.
- 본문 요약에는 중요한 정보를 깔끔하게 정리해줘.
- 본문 에서 강조하는 내용은 반드시 핵심 포인트 항목에 정리해줘.
- <출력 형식> 태그 내에 있는 것만 마크다운 코드 블럭으로 감싸지 말고 응답해줘.
- 노션에 작성할거야.
- 글씨를 굵게 표현하는 "**"표시는 제거해줘

<출력 형식>

## 🔍 내용 요약

(전체 내용을 간략히 요약)

## 💡 핵심 포인트

- (핵심 포인트 정리)

## 📚 기술 세부 내용

### 1️⃣ (제목)

- (내용)

</출력 형식>

**[본문]**
{text}
"""
        response = model.generate_content(prompt)
        return response.text.strip() if response.text else "상세 분석 실패 (내용 없음)"

    except Exception as e:
        print(f"Gemini API (details_text) 호출 중 오류 발생: {e}")
        send_slack_message(f"[ERROR] Gemini API (details_text) 호출 중 오류 발생: {e}")
        return "상세 분석 실패 (API 오류)"


def summarize_text(text):
    """
    입력된 텍스트 [본문]를 바탕으로 Gemini API를 사용하여
    300자 이내의 간결한 요약문을 생성합니다.
    """
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash-lite") # 요약에는 flash 모델이 효율적입니다.

        prompt = f"""
당신은 핵심 정보를 정확하고 명료하게 전달하는 요약 AI입니다. 제시된 [본문] 텍스트를 바탕으로, 객관적인 사실에 기반하여 핵심 내용을 간결하게 전달하는 뉴스 보도와 같이 독자들이 사건의 핵심을 쉽게 파악하도록 돕는 역할을 수행합니다.

먼저, 전달받은 [본문] 내용을 어떻게 요약하여 독자들에게 오해 없이 명확하게 전달할지 그 구성을 면밀히 검토합니다. 이 과정에서 핵심 메시지를 정확히 추출하고, 이를 가장 간결하고 명료한 방식으로 전달할 방법을 구상합니다.

그런 다음, 다음 지침에 따라 요약 결과물을 한국어로 작성해 주십시오.

내용의 핵심을 정확히 짚어주세요: 중복되는 내용은 생략하되, 여러 번 언급된 중요한 정보는 그 중요도를 반영하여 요약에 비중을 둡니다.
개념과 논거 중심으로 설명해주세요: 단순한 사건 나열이나 사례 언급보다는, 그 안에 담긴 개념과 주장의 근거를 명확히 드러내어 독자들의 이해를 돕습니다.
쉽고 명확한 표현을 사용해주세요: 전문 용어나 지나치게 어려운 단어 사용은 최소화하고, 독자들이 쉽게 이해할 수 있는 표준적이고 명확한 단어를 선택합니다.
능동적이고 간결한 문장을 사용해주세요: 가급적 능동태를 사용하여 문장의 의미를 명확히 하고, 수동적인 표현이나 불필요한 수식은 지양하여 간결성을 높입니다.
객관적이고 건설적인 관점을 유지해주세요: 문제 상황이나 도전을 다룰 때에도, 감정적인 표현을 배제하고 객관적인 사실에 기반하여 상황을 전달하되, 가능한 경우 건설적인 해결 방향이나 긍정적인 가능성을 간략히 언급할 수 있습니다. 지나치게 딱딱하거나 냉담한 어투는 피하고, 정보를 명확히 전달하는 데 집중합니다.
간결하고 명료한 뉴스 형식을 따릅니다: 각 문장은 핵심 정보를 담아 짧고 명확하게 구성하며, 불필요한 미사여구나 감정적 표현 없이 사실을 전달하는 데 집중합니다.
가독성 좋게 줄바꿈하고, 전체 요약의 분량은 공백 포함 200자 이상 300자 이내로 작성합니다.
글씨를 굵게 표현하는 "**"표시는 제거해줘

[본문]
{text}
[/본문]
"""
        response = model.generate_content(prompt)
        return response.text.strip() if response.text else "요약 실패 (내용 없음)"

    except Exception as e:
        print(f"Gemini API (summarize_text) 오류: {e}")
        send_slack_message(f"[ERROR] Gemini API (summarize_text) 호출 중 오류 발생: {e}")
        return "요약 실패 (API 오류)"


def CVE_details_text(text):
    """
    입력된 텍스트(CVE (Common Vulnerabilities and Exposures))를 바탕으로 Gemini API를 사용하여
    CVE 관련 블로그 글을 생성합니다. (기존 블로그 글 형식 프롬프트 사용)
    """
    try:
        genai.configure(api_key=GEMINI_API_KEY) # GEMINI_API_TOKEN 사용
        model = genai.GenerativeModel("gemini-2.5-flash")

        # CVE 내용에 대한 블로그 글을 생성하도록 프롬프트를 조정합니다.
        # 기존 블로그 프롬프트의 {주제} 부분에 'CVE (Common Vulnerabilities and Exposures)'를 명시하고,
        # 본문 내용을 기반으로 글을 작성하도록 합니다.
        prompt = f"""
지금부터 최근 7일 간 발표 된 CVE (Common Vulnerabilities and Exposures)에 관한 기술적 내용을 설명하는 블로그 글을 써 주세요. 다음 **[CVE 본문]** 내용을 바탕으로 작성해야 합니다. 분량은 대략 4,000단어.

본문에 들어가기 전에 먼저 검색 노출에 유리한 롱테일 키워드 10개 정도를 추립니다.
그 키워드를 골고루 녹여 넣을 개요를 잡습니다. 구조는 다음을 참고하세요.
H1 헤드라인 1개
H2·H3 소제목을 섞어서 3개 이상
글은 개요 순서를 그대로 따라가며 작성합니다. 특히 각 H2 단락에는 앞서 고른 키워드 중 하나를 자연스럽게 배치해 주세요.
문체는 친구에게 설명하듯 편안하고 능동적으로. 곳곳에 질문･비유를 넣어 공감할 수 있게 만듭니다. 단, 반말 사용 금지.
끝부분에 핵심을 정리한 결론을 붙이고, 독자가 가장 궁금해할 만한 질문･답변 3개를 추가합니다.
제목과 모든 헤딩(H 태그)은 굵게 표기하지만, 본문 속 키워드 자체는 굵게 처리하지 않습니다.
롱테일 키워드, 개요는 출력에서 제외 해주세요.
기술적 용어나 고유명사같은건 영어 그대로 사용해줘.
다른 글을 표절하지 말고, 순전히 당신의 표현으로만 작성해 주세요.
작성 된 글을 분석하여 내용에 맞는 제목을 제시해주세요

<출력 형식>

--제목 start---
(포스트 내용에 맞는 제목을 제시("**"표시는 제거))
---제목 end---
--본문 start---
(본문 내용 작성)
---본문 end---
</출력 형식>

**[CVE 본문]**
{text}
"""
        response = model.generate_content(prompt)
        
        full_response = response.text.strip()
        
        # 제목과 본문을 정규표현식으로 파싱
        title_match = re.search(r'--제목 start---\s*\n(.*?)\n---제목 end---', full_response, re.DOTALL)
        body_match = re.search(r'--본문 start---\s*\n(.*?)\n---본문 end---', full_response, re.DOTALL)
        
        generated_title = title_match.group(1).strip() if title_match else "제목 없음"
        generated_body = body_match.group(1).strip() if body_match else "본문 내용 없음"

        return generated_title, generated_body

    except Exception as e:
        print(f"Gemini API (CVE_details_text) 호출 중 오류 발생: {e}")
        send_slack_message(f"[ERROR] Gemini API (CVE_details_text) 호출 중 오류 발생: {e}")
        return "블로그 글 생성 실패 (API 오류)", "블로그 글 생성 실패 (API 오류)"

def extract_and_explain_keywords(text):
    """
    입력된 텍스트를 바탕으로 Gemini API를 사용하여
    최근 7일간의 주요 기술 키워드 10개와 각 설명을 생성합니다.
    """
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash") # 상세한 설명을 위해 pro 모델 사용

        prompt = f"""
다음은 최근 7일간의 정보 보안 및 기술 관련 뉴스 또는 보고서 내용입니다.
이 내용을 분석하여 **가장 중요한 기술 키워드 10개**를 추출하고, 각 키워드에 대해 2~3 문장으로 간결하고 명확하게 설명해 주세요.

<출력 형식>
## 🌟 주간 기술 키워드

- **[키워드 1]**: (설명)
- **[키워드 2]**: (설명)
...
- **[키워드 10]**: (설명)
</출력 형식>

**[본문]**
{text}
"""
        response = model.generate_content(prompt)
        return response.text.strip() if response.text else "기술 키워드 추출 및 설명 실패 (내용 없음)"

    except Exception as e:
        print(f"Gemini API (extract_and_explain_keywords) 호출 중 오류 발생: {e}")
        send_slack_message(f"[ERROR] Gemini API (extract_and_explain_keywords) 호출 중 오류 발생: {e}")
        return "기술 키워드 추출 및 설명 실패 (API 오류)"
    
def generate_weekly_tech_blog_post(topic_or_combined_text):
    """
    주어진 주제 또는 결합된 텍스트를 바탕으로
    블로그 글 작성 프롬프트에 따라 롱테일 키워드 기반의 기술 블로그 글을 생성합니다.
    """
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.5-flash") # 긴 글 생성을 위해 Pro 모델 권장

        # {주제} 부분에 들어갈 내용을 프롬프트 템플릿에 맞춰 조정합니다.
        # 여기서는 topic_or_combined_text를 바로 '주제'로 사용하거나,
        # '주제'가 아닌 '본문'에 해당하는 정보로 넘길 수 있습니다.
        # 주간 이슈라면, 최근 7일간의 요약된 정보가 '본문'이 될 수 있습니다.
        # 아래 프롬프트는 '기술적 내용'을 입력으로 받아 처리하도록 구성됩니다.

        # 프롬프트 예시: "최근 일주일간의 보안 이슈"를 주제로 받거나,
        #                 "최근 보안 뉴스 요약: [실제 요약 내용]"을 본문으로 받을 수 있습니다.
        # 여기서는 topic_or_combined_text를 '주제'와 '본문'에 모두 활용하여
        # Gemini가 이를 바탕으로 글을 생성하도록 합니다.
        # 만약 {주제}를 별도로 지정하고 싶다면, 함수 인자를 추가해야 합니다.
        
        # 블로그 글 작성 프롬프트
        prompt = f"""
지금부터 {topic_or_combined_text}에 관한 기술적 내용을 설명하는 블로그 글을 써 주세요. 분량은 대략 4,000단어.

본문에 들어가기 전에 먼저 검색 노출에 유리한 롱테일 키워드 10개 정도를 추립니다.
그 키워드를 골고루 녹여 넣을 개요를 잡습니다. 구조는 다음을 참고하세요.
H1 헤드라인 1개
H2·H3 소제목을 섞어서 3개 이상
글은 개요 순서를 그대로 따라가며 작성합니다. 특히 각 H2 단락에는 앞서 고른 키워드 중 하나를 자연스럽게 배치해 주세요.
문체는 친구에게 설명하듯 편안하고 능동적으로. 곳곳에 질문･비유를 넣어 공감할 수 있게 만듭니다. 단, 반말 사용 금지.
끝부분에 핵심을 정리한 결론을 붙이고, 독자가 가장 궁금해할 만한 질문･답변 3개를 추가합니다.
제목과 모든 헤딩(H 태그)은 굵게 표기하지만, 본문 속 키워드 자체는 굵게 처리하지 않습니다.
롱테일 키워드, 개요는 출력에서 제외 해주세요.
기술적 용어나 고유명사같은건 영어 그대로 사용해줘.
다른 글을 표절하지 말고, 순전히 당신의 표현으로만 작성해 주세요.
작성 된 글을 분석하여 내용에 맞는 제목을 제시해주세요

<출력 형식>

--제목 start---
(포스트 내용에 맞는 제목을 제시("**"표시는 제거))
---제목 end---
--본문 start---
(본문 내용 작성)
---본문 end---
</출력 형식>
"""
        response = model.generate_content(prompt)
        
        # 응답 텍스트에서 제목과 본문을 분리
        full_response = response.text.strip()
        
        title_match = re.search(r'--제목 start---\s*\n(.*?)\n---제목 end---', full_response, re.DOTALL)
        body_match = re.search(r'--본문 start---\s*\n(.*?)\n---본문 end---', full_response, re.DOTALL)
        
        generated_title = title_match.group(1).strip() if title_match else "제목 없음"
        generated_body = body_match.group(1).strip() if body_match else "본문 내용 없음"

        return generated_title, generated_body

    except Exception as e:
        print(f"Gemini API (generate_weekly_tech_blog_post) 호출 중 오류 발생: {e}")
        send_slack_message(f"[ERROR] Gemini API (generate_weekly_tech_blog_post) 호출 중 오류 발생: {e}")
        return "블로그 글 생성 실패 (API 오류)", "블로그 글 생성 실패 (API 오류)"