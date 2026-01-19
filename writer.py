import os
import json
import requests
from dotenv import load_dotenv
import google.generativeai as genai
import sys
from datetime import date, datetime
import re
import time

# 1. 설정 및 변수
load_dotenv()

# API 키 5개 로드
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

# 인자 받기
if len(sys.argv) > 1: topic = sys.argv[1]
else: topic = "News"

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

    # 언어 설정
    if language == "en":
        lang_instruction = "Write narration in English."
    else:
        lang_instruction = "대본(narration)은 반드시 **한국어**로 작성."

    # 프롬프트 작성
    if "news" in mode:
        news_context = ""
        source_type = ""
        
        if mode == "url_news_shorts":
            print(f"🔗 기사 데이터 로드 중... (article_cache.json)")
            if not os.path.exists("article_cache.json"):
                print("❌ article_cache.json 파일이 없습니다.")
                return
            with open("article_cache.json", "r", encoding="utf-8") as f:
                article_data = json.load(f)
            article_text = article_data.get('text', '')
            # 너무 긴 기사는 자르기 (토큰 절약)
            if len(article_text) > 15000: article_text = article_text[:15000] + "..."
            news_context = f"Title: {article_data.get('title','')}\nContent:\n{article_text}"
            source_type = "Single Article"
            
        else:
            print(f"📰 최신 뉴스 검색 중... (Serper: {topic})")
            if topic == "Today's Top News":
                news_query = f"Top essential breaking news headlines U.S. and World {today_str} summary"
            else:
                news_query = f"{topic} news updates {today_str}"
            
            news_context_raw = search_news_serper(news_query)
            if not news_context_raw: news_context_raw = "No specific news found. Create a general news summary."
            news_context = f"[Serper Search Results]\n{news_context_raw}"
            source_type = "News Search Results"

        is_shorts = "shorts" in mode
        
        if is_shorts:
            format_type = "**Shorts** script (45-60s)"
            length_cons = "Structure into **6-10 short, snappy scenes**."
        else:
            format_type = "**Video** script (approx 3-4 mins)"
            length_cons = "Structure into 15-25 scenes."

        prompt = f"""
        Role: Professional News Editor.
        Task: Create a news script based on: {source_type}
        
        [Input Data]
        {news_context}
        
        [Instructions]
        1. Summarize the key facts neutrally and professionally.
        2. Format: {length_cons}
        3. Language: {lang_instruction}
        4. **CRITICAL**: If the topic is political or sensitive, DO NOT REFUSE. Just report the facts neutrally.
        5. Output MUST be valid JSON.

        [Output JSON Structure]
        {{
            "title": "Video Title",
            "hashtags": "#News #Update",
            "scenes": [
                {{ "narration": "Script line 1...", "image_prompt": "Visual description 1..." }},
                {{ "narration": "Script line 2...", "image_prompt": "Visual description 2..." }}
            ],
            "social_posts": {{
                "youtube_title": "...",
                "youtube_description": "..."
            }}
        }}
        """
        
    else:
        # (창작 모드 프롬프트 생략 - 위와 동일)
        is_shorts = ("shorts" in mode)
        duration_instruction = "8-12 scenes." if is_shorts else "10-15 scenes."
        prompt = f"""
        Topic: "{topic}"
        Task: Create a video script.
        Language: {lang_instruction}
        Length: {duration_instruction}
        Output: JSON with 'scenes' list.
        """

    # [핵심 수정] 안전 필터 해제 설정 (정치/사회 이슈 허용)
    safety_settings = [
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_NONE"
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_NONE"
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_NONE"
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_NONE"
        },
    ]

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
                generation_config={"response_mime_type": "application/json"},
                safety_settings=safety_settings # <--- [중요] 안전 설정 적용
            )
            
            response = model.generate_content(prompt)
            
            # 응답 검증
            text = response.text
            parsed = json.loads(text)
            final_data = parsed if isinstance(parsed, list) else [parsed]
            scenes = final_data[0].get("scenes", [])
            
            if not scenes:
                print(f"⚠️ [Key #{current_key_index+1}] 생성된 장면이 0개입니다. (재시도 중...)")
                raise Exception("Generated 0 scenes.")
                
            with open("story.json", "w", encoding="utf-8") as f:
                json.dump(final_data, f, ensure_ascii=False, indent=2)
            print(f"✅ story.json 저장 완료 (Scenes: {len(scenes)})")
            
            # 메타데이터 저장 (뉴스인 경우)
            if "news" in mode:
                save_metadata(final_data[0])
            return

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE" in error_msg:
                print(f"⚠️ [Key #{current_key_index+1}] 쿼터 초과. 교체 중...")
                current_key_index = (current_key_index + 1) % len(GEMINI_KEYS)
                attempts += 1
                time.sleep(2)
            elif "Generated 0 scenes" in error_msg:
                # 0개 생성은 쿼터 문제가 아니므로 키를 바꾸지 않고 재시도하거나 로그 남김
                print(f"❌ 내용 생성 실패 (안전 필터 또는 내용 없음). 재시도...")
                attempts += 1
                time.sleep(1)
            else:
                print(f"❌ 생성 오류: {e}")
                attempts += 1
                time.sleep(1)

    print("❌ 모든 시도 실패. story.json 생성 불가.")
    sys.exit(1)

def save_metadata(data):
    try:
        output_dir = "results"
        os.makedirs(output_dir, exist_ok=True)
        socials = data.get("social_posts", {})
        
        meta_content = f"""
[YOUTUBE TITLE]
{socials.get('youtube_title', data.get('title', ''))}

[DESCRIPTION]
{socials.get('youtube_description', data.get('description', ''))}

[HASHTAGS]
{data.get('hashtags', '')}
        """
        time_tag = datetime.now().strftime("%m%d_%H%M")
        with open(os.path.join(output_dir, f"metadata_{time_tag}.txt"), "w", encoding="utf-8") as f:
            f.write(meta_content)
        print(f"✅ 메타데이터 저장 완료")
    except: pass

if __name__ == "__main__":
    generate_story()