import os
from dotenv import load_dotenv
import google.generativeai as genai

# .env 파일에서 환경 변수 로드
load_dotenv()

# API 키 가져오기
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("오류: .env 파일에서 GEMINI_API_KEY를 찾을 수 없습니다.")
    print("팁: .env 파일을 만들고 GEMINI_API_KEY=your_key_here 형식으로 저장했는지 확인하세요.")
else:
    try:
        # Gemini 설정
        genai.configure(api_key=api_key)

        # 모델 초기화 (Gemini Pro)
        model = genai.GenerativeModel('gemini-2.0-flash')

        # 메시지 전송
        prompt = "안녕? 나는 너의 주인이야. 짧고 멋있게 충성을 맹세해!"
        print(f"Me: {prompt}")

        response = model.generate_content(prompt)
        
        # 응답 출력
        print(f"Gemini: {response.text}")

    except Exception as e:
        print(f"에러가 발생했습니다: {e}")
