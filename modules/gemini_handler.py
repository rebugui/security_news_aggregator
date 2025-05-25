# modules/gemini_handler.py
"""
Google Gemini API를 사용하여 텍스트를 요약하고 상세 분석하는 모듈입니다.
"""

import google.generativeai as genai
from config import GEMINI_API_KEY
from .utils import send_slack_message

def details_text(text):
    """
    입력된 텍스트(뉴스 본문)를 바탕으로 Gemini API를 사용하여
    정보 보안 기술에 대한 상세 설명을 생성합니다. (상세 분석용 프롬프트 사용)
    """
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-pro-latest") # 모델명은 최신 버전으로 사용하는 것을 권장합니다.
        
        prompt = f"""
정보 보안 관련 기술에 대한 상세 설명을 제공하는 블로그 작성 AI입니다.

제시된 **[뉴스 본문]**에 언급된 보안 관련 기술을 분석하여 자세한 설명을 작성하십시오.

필요 없는 정보는 제거해줘. 작성 시 이모지를 활용해 깔끔하고 구체적으로 정리해줘.

<핵심 참고 사항>

- 기술적 용어나 고유명사같은건 영어 그대로 사용해줘.
- 세부내용에는 최대한 놓치는 정보 없이 자세하게 정리해줘.
- 뉴스요약에는 중요한 정보를 깔끔하게 정리해줘.
- 뉴스에서 강조하는 내용은 반드시 핵심 포인트 항목에 정리해줘.
- <출력 형식> 태그 내에 있는 것만 마크다운 코드 블럭으로 감싸지 말고 응답해줘.
- 노션에 작성할거야.
- 글씨를 굵게 표현하는 "**"표시는 제거해줘

<출력 형식>

## 🔍 뉴스 요약

(뉴스 전체 내용을 간략히 요약)

## 💡 핵심 포인트

- (뉴스 핵심 포인트 정리)

## 📚 기술 세부 내용

### 1️⃣ (제목)

- (내용)

</출력 형식>

**[뉴스 본문]**
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
    입력된 텍스트(뉴스 본문)를 바탕으로 Gemini API를 사용하여
    300자 이내의 간결한 요약문을 생성합니다.
    """
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash-latest") # 요약에는 flash 모델이 효율적입니다.

        prompt = f"""
당신은 핵심 정보를 정확하고 명료하게 전달하는 뉴스 요약 AI입니다. 제시된 뉴스 텍스트를 바탕으로, 객관적인 사실에 기반하여 핵심 내용을 간결하게 전달하는 뉴스 보도와 같이 독자들이 사건의 핵심을 쉽게 파악하도록 돕는 역할을 수행합니다.

먼저, 전달받은 뉴스 내용을 어떻게 요약하여 독자들에게 오해 없이 명확하게 전달할지 그 구성을 면밀히 검토합니다. 이 과정에서 핵심 메시지를 정확히 추출하고, 이를 가장 간결하고 명료한 방식으로 전달할 방법을 구상합니다.

그런 다음, 다음 지침에 따라 요약 결과물을 한국어로 작성해 주십시오.

내용의 핵심을 정확히 짚어주세요: 중복되는 내용은 생략하되, 여러 번 언급된 중요한 정보는 그 중요도를 반영하여 요약에 비중을 둡니다.
개념과 논거 중심으로 설명해주세요: 단순한 사건 나열이나 사례 언급보다는, 그 안에 담긴 개념과 주장의 근거를 명확히 드러내어 독자들의 이해를 돕습니다.
쉽고 명확한 표현을 사용해주세요: 전문 용어나 지나치게 어려운 단어 사용은 최소화하고, 독자들이 쉽게 이해할 수 있는 표준적이고 명확한 단어를 선택합니다.
능동적이고 간결한 문장을 사용해주세요: 가급적 능동태를 사용하여 문장의 의미를 명확히 하고, 수동적인 표현이나 불필요한 수식은 지양하여 간결성을 높입니다.
객관적이고 건설적인 관점을 유지해주세요: 문제 상황이나 도전을 다룰 때에도, 감정적인 표현을 배제하고 객관적인 사실에 기반하여 상황을 전달하되, 가능한 경우 건설적인 해결 방향이나 긍정적인 가능성을 간략히 언급할 수 있습니다. 지나치게 딱딱하거나 냉담한 어투는 피하고, 정보를 명확히 전달하는 데 집중합니다.
간결하고 명료한 뉴스 형식을 따릅니다: 각 문장은 핵심 정보를 담아 짧고 명확하게 구성하며, 불필요한 미사여구나 감정적 표현 없이 사실을 전달하는 데 집중합니다.
가독성 좋게 줄바꿈하고, 전체 요약의 분량은 공백 포함 200자 이상 300자 이내로 작성합니다.

[뉴스본문]
{text}
[/뉴스본문]
"""
        response = model.generate_content(prompt)
        return response.text.strip() if response.text else "요약 실패 (내용 없음)"

    except Exception as e:
        print(f"Gemini API (summarize_text) 오류: {e}")
        send_slack_message(f"[ERROR] Gemini API (summarize_text) 호출 중 오류 발생: {e}")
        return "요약 실패 (API 오류)"
