import os
import json
import requests
from dotenv import load_dotenv
import google.generativeai as genai
import sys
from datetime import date, datetime
import re
import time

load_dotenv()

GEMINI_KEYS = []
if os.environ.get("GEMINI_API_KEY"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY"))
if os.environ.get("GEMINI_API_KEY_2"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY_2"))
if os.environ.get("GEMINI_API_KEY_3"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY_3"))
if os.environ.get("GEMINI_API_KEY_4"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY_4"))
if os.environ.get("GEMINI_API_KEY_5"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY_5"))

if not GEMINI_KEYS:
    print("❌ 오류: .env 파일에서 GEMINI_API_KEY를 찾을 수 없습니다.")
    sys.exit(1)

current_key_index = 0
print(f"🔑 [Writer] 로드된 Gemini API 키 개수: {len(GEMINI_KEYS)}개")

if len(sys.argv) > 1: topic = sys.argv[1]
else: topic = "서기 2050년, 인간과 사랑에 빠진 AI 로봇"

mode = "video"
if len(sys.argv) > 2: mode = sys.argv[2]

language = "ko"
if len(sys.argv) > 3: language = sys.argv[3]

def search_news_serper(query):
    url = "https://google.serper.dev/news"
    serper_key = os.getenv("SERPER_API_KEY")
    if not serper_key: return ""
    payload = json.dumps({"q": query, "gl": "us", "hl": "en", "num": 20})
    headers = {'X-API-KEY': serper_key, 'Content-Type': 'application/json'}
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        data = response.json()
        news_list = []
        if "news" in data:
            for item in data["news"]:
                news_list.append(f"- {item.get('title','')}: {item.get('snippet','')}")
        return "\n".join(news_list)
    except: return ""

def generate_story():
    global current_key_index
    today_str = date.today().strftime("%Y-%m-%d")

    # 프롬프트 설정
    if language == "en":
        lang_instruction = "Write narration in English."
    else:
        lang_instruction = "대본(narration)은 반드시 **한국어**로 작성."

    # 모드별 프롬프트
    if "news" in mode:
        # (뉴스 관련 로직은 기존과 동일)
        is_shorts = "shorts" in mode
        prompt = f"""
        Role: Professional News Editor.
        Task: Create a news script based on the topic: "{topic}".
        Format: JSON only.
        Constraints:
        1. {lang_instruction}
        2. Create 5-8 scenes.
        3. Strict JSON format.
        """
        # (뉴스 모드 상세 프롬프트는 생략, 창작 모드 집중)
    else:
        # [창작 모드] 프롬프트 강화
        is_shorts = ("shorts" in mode)
        duration_instruction = "Make it fast-paced (Shorts style). 8-12 scenes." if is_shorts else "Standard video pace. 10-15 scenes."
        
        prompt = f"""
        You are a creative storyteller and video director.
        
        Topic: "{topic}"
        Task: Create a video script for the above topic.
        
        [Format Requirements]
        - Output MUST be valid JSON.
        - Structure:
        {{
            "title": "Video Title",
            "scenes": [
                {{ "narration": "Script line 1...", "image_prompt": "Visual description 1..." }},
                {{ "narration": "Script line 2...", "image_prompt": "Visual description 2..." }}
            ]
        }}
        
        [Content Requirements]
        1. Language: {lang_instruction}
        2. Length: {duration_instruction}
        3. **CRITICAL**: Ensure 'scenes' list is NOT empty. Generate at least 5 scenes.
        4. No markdown, no extra text. Just JSON.
        """

    # 모델 실행 (2.0 Flash)
    MODEL_NAME = "gemini-2.0-flash"
    print(f"🤖 Gemini 모델 호출 중... (Model: {MODEL_NAME})")
    
    attempts = 0
    max_attempts = len(GEMINI_KEYS) * 2
    
    while attempts < max_attempts:
        current_key = GEMINI_KEYS[current_key_index]
        try:
            genai.configure(api_key=current_key)
            model = genai.GenerativeModel(
                model_name=MODEL_NAME, 
                generation_config={"response_mime_type": "application/json"}
            )
            response = model.generate_content(prompt)
            
            # 응답 검증
            text = response.text
            parsed = json.loads(text)
            
            # 리스트면 첫번째 요소, 아니면 그대로
            final_data = parsed if isinstance(parsed, list) else [parsed]
            scenes = final_data[0].get("scenes", [])
            
            if not scenes:
                raise Exception("Generated 0 scenes.")
                
            with open("story.json", "w", encoding="utf-8") as f:
                json.dump(final_data, f, ensure_ascii=False, indent=2)
            print(f"✅ story.json 저장 완료 (Scenes: {len(scenes)})")
            return

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE" in error_msg:
                print(f"⚠️ [Key #{current_key_index+1}] 쿼터 초과. 교체 중...")
                current_key_index = (current_key_index + 1) % len(GEMINI_KEYS)
                attempts += 1
                time.sleep(2)
            else:
                print(f"❌ 생성 오류: {e}")
                attempts += 1
                time.sleep(1)

    print("❌ 모든 시도 실패. story.json 생성 불가.")
    sys.exit(1)

if __name__ == "__main__":
    generate_story()