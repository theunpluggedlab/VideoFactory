import os
import json
import requests
from dotenv import load_dotenv
import google.generativeai as genai
import sys
from datetime import date, datetime
import re

# 1. 설정 및 변수
load_dotenv()

# API 키 리스트 로드 (Rotation - 4개)
GEMINI_KEYS = []
if os.environ.get("GEMINI_API_KEY"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY"))
if os.environ.get("GEMINI_API_KEY_2"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY_2"))
if os.environ.get("GEMINI_API_KEY_3"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY_3"))
if os.environ.get("GEMINI_API_KEY_4"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY_4"))

if not GEMINI_KEYS:
    print("❌ 오류: .env 파일에서 GEMINI_API_KEY를 찾을 수 없습니다.")
    sys.exit(1)

current_key_index = 0
print(f"🔑 [Writer] 로드된 Gemini API 키 개수: {len(GEMINI_KEYS)}")

# 주제 및 모드 설정
if len(sys.argv) > 1:
    topic = sys.argv[1]
else:
    topic = "서기 2050년, 인간과 사랑에 빠진 AI 로봇"

mode = "video"
if len(sys.argv) > 2:
    mode = sys.argv[2]

language = "ko"
if len(sys.argv) > 3:
    language = sys.argv[3]

def search_news_serper(query):
    """Serper API를 사용하여 뉴스 검색 (정보량 증대: 20개)"""
    url = "https://google.serper.dev/news"
    serper_key = os.getenv("SERPER_API_KEY")
    if not serper_key:
        print("⚠️ SERPER_API_KEY가 없습니다. 뉴스 검색을 건너뜁니다.")
        return ""
        
    payload = json.dumps({
        "q": query, "gl": "us", "hl": "en", "num": 20 
    })
    headers = {'X-API-KEY': serper_key, 'Content-Type': 'application/json'}
    
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        data = response.json()
        news_list = []
        if "news" in data:
            for item in data["news"]:
                source = item.get("source", "")
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                date_ago = item.get("date", "")
                news_list.append(f"- [{source} | {date_ago}] {title}: {snippet}")
        return "\n".join(news_list)
    except Exception as e:
        print(f"❌ Serper 뉴스 검색 실패: {e}")
        return ""

def generate_story():
    global current_key_index
    
    response = None 
    prompt = ""
    
    # 언어 설정
    if language == "en":
        narration_lang_instruction = "Write the narration script in **English**."
    else:
        narration_lang_instruction = "대본(narration)을 **한국어**로 작성해. (단, 채널명 'Flash News Bite'는 영어 그대로 유지)"

    today_str = date.today().strftime("%Y-%m-%d")

    # ---------------------------------------------------------
    # 2. 프롬프트 작성 로직
    # ---------------------------------------------------------
    if "news" in mode:
        # 1) 뉴스 모드 (Serper 사용)
        news_context = ""
        source_type = ""
        
        if mode == "url_news_shorts":
            # URL 모드
            print(f"🔗 기사 데이터 로드 중... (article_cache.json)")
            if not os.path.exists("article_cache.json"):
                print("❌ article_cache.json 파일이 없습니다.")
                return
            with open("article_cache.json", "r", encoding="utf-8") as f:
                article_data = json.load(f)
            article_text = article_data.get('text', '')
            if len(article_text) > 20000: article_text = article_text[:20000] + "..."
            news_context = f"Title: {article_data.get('title','')}\nContent:\n{article_text}"
            source_type = "Single Article"
            
        else:
            # 일반 뉴스 모드 (Serper 검색)
            print(f"📰 최신 뉴스 검색 중... (Serper: {topic})")
            
            if topic == "Today's Top News":
                news_query = f"Top essential breaking news headlines U.S. and World {today_str} summary"
            else:
                news_query = f"{topic} news updates {today_str}"
            
            news_context_raw = search_news_serper(news_query)
            if not news_context_raw: news_context_raw = "뉴스 검색 실패. 일반적인 최신 뉴스로 생성."
            news_context = f"[Serper Search Results]\n{news_context_raw}"
            source_type = "News Search Results"

        # 포맷 설정
        is_shorts = "shorts" in mode
        
        if is_shorts:
            format_type = "**Shorts** script (45-60s)"
            length_cons = "Strictly 45-60 seconds. Structure into **8-12 short, snappy scenes**."
        else:
            format_type = "**Video** script (approx 3-4 mins)"
            length_cons = "Approx 3-4 minutes. Structure into 15-25 scenes."

        channel_desc = "Stay instantly informed with Flash News Bite! We bring you the day’s most important news, summarized in quick, easy-to-watch videos. Perfect for viewers who want authentic updates on top world, U.S., and trending stories—without the clutter."

        prompt = f"""
        You are the lead editor and social media manager for the news channel "**Flash News Bite**".
        Channel Mission: "{channel_desc}"
        
        Task: Generate a complete content package for a YouTube {format_type}.
        Based on: {source_type} data provided below.
        Date: {today_str}
        
        [Input Data]
        {news_context}
        
        [Instructions & Constraints]
        1. **Content**: Focus ONLY on today's Top Must-Know events.
        2. **Format Constraint**: {length_cons}
        3. **Scene Pacing**: Each scene's narration must be **maximum 2 sentences long**.
        4. **Language**: {narration_lang_instruction}
        5. **Formatting**: NO EMOJIS in narration. Wrap **KEYWORDS** in asterisks `*`.
        
        6. **MANDATORY INTRO (Scene 1)**: 
           - Start with a short, punchy hook (1 sentence) welcoming viewers to "**Flash News Bite**".
           - **CRITICAL**: Vary the wording every time to sound fresh.
           - Image Prompt: "Flash News Bite logo, news studio background, professional, 3d render"

        7. **MANDATORY OUTRO (Last Scene)**: 
           - End with a dynamic sign-off mentioning "**Flash News Bite**".
           - Ask to Like, Subscribe, and Comment.
           - **CRITICAL**: Vary the wording every time.
           - Image Prompt: "YouTube Subscribe button and Like icon, Flash News Bite theme, neon lighting, high quality"
        
        [Output Requirement - Social Media Package (CRITICAL)]
        You must generate optimized posts for EACH platform in the `social_posts` JSON section.
        Use English for social posts unless the topic is local.
        
        1. **YouTube Post**:
           - **Title**: Clickable, under 100 chars, include #Shorts + keywords.
           - **Description**: 
             - Hook paragraph.
             - Detailed summary body (2 paragraphs).
             - Engagement question (e.g., "What do you think?").
             - **CTAs**: Use 👉 icon. (e.g., "👉 Hit LIKE, 👉 SUBSCRIBE, 👉 SHARE").
             - **Hashtags**: List of relevant tags.
        
        2. **X (Twitter)**: Under 280 chars, punchy summary, relevant emojis, 3-5 hashtags.
        3. **Threads**: Conversational tone, slightly longer than X, storytelling style, hashtags.
        4. **Instagram**: Visual hook line, detailed caption, question for engagement. CTAs: "❤️ Save this post", "💬 Drop your thoughts". Wall of hashtags.
        5. **TikTok**: Very short hook, "Watch till the end", viral tags like #fyp #foryou #breakingnews.

        Strictly output valid JSON:
        {{
            "title": "YouTube Title",
            "description": "YouTube Description",
            "hashtags": "YouTube Hashtags",
            "scenes": [ ... ],
            "social_posts": {{
                "youtube_title": "...",
                "youtube_description": "...",
                "x_post": "...",
                "threads_post": "...",
                "instagram_caption": "...",
                "tiktok_caption": "..."
            }}
        }}
        """
        
    else:
        # 창작 모드
        is_shorts = ("shorts" in mode) or ("shorts" in topic.lower())
        duration_instruction = "Shorts 모드: 50초 이내, 장면 8개 이상." if is_shorts else ""
        prompt = f"""
        Topic: "{topic}"
        Create a story script.
        {duration_instruction}
        Language: {narration_lang_instruction}
        Output strictly JSON.
        """

    # ---------------------------------------------------------
    # 3. 모델 실행 (Key Rotation)
    # ---------------------------------------------------------
    print(f"🤖 Gemini 모델 호출 중... (Mode: {mode})")
    
    attempts = 0
    max_attempts = len(GEMINI_KEYS)
    
    while attempts < max_attempts:
        current_key = GEMINI_KEYS[current_key_index]
        try:
            # Writer는 기존 google-generativeai 사용 (안정성)
            genai.configure(api_key=current_key)
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.95, "top_k": 40, 
                "max_output_tokens": 8192, "response_mime_type": "application/json"
            }
            model = genai.GenerativeModel(
                model_name="gemini-2.0-flash", 
                generation_config=generation_config
            )
            
            response = model.generate_content(prompt)
            break 
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "QuotaExceeded" in error_msg:
                print(f"⚠️ [Key {current_key_index+1}] 쿼터 초과! 다음 키로 교체...")
                current_key_index = (current_key_index + 1) % len(GEMINI_KEYS)
                attempts += 1
                continue
            else:
                print(f"❌ API 호출 중 오류 발생: {e}")
                attempts += 1
                continue

    if not response:
        print("❌ 실패: 모든 API 키가 소진되었거나 응답을 받지 못했습니다.")
        sys.exit(1)

    text = response.text
    text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
        
    try:
        parsed_data = json.loads(text)
        final_data = parsed_data if isinstance(parsed_data, list) else [parsed_data]
        
        with open("story.json", "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)
        print(f"✅ story.json 저장 완료 (Scenes: {len(final_data[0].get('scenes', []))})")
        
        if "news" in mode:
            output_dir = "results"
            os.makedirs(output_dir, exist_ok=True)
            
            # [핵심] JSON에서 소셜 미디어 데이터 추출
            socials = parsed_data.get("social_posts", {})
            
            # [메타데이터 저장 로직 강화]
            meta_content = ""
            
            # 1. YouTube
            yt_title = socials.get("youtube_title") or parsed_data.get("title", "")
            yt_desc = socials.get("youtube_description") or parsed_data.get("description", "")
            
            meta_content += "========================================\n"
            meta_content += "[YOUTUBE]\n"
            meta_content += f"TITLE:\n{yt_title}\n\n"
            meta_content += f"DESCRIPTION:\n{yt_desc}\n\n"
            meta_content += f"HASHTAGS:\n{parsed_data.get('hashtags', '')}\n"
            meta_content += "========================================\n\n"
            
            # 2. X (Twitter)
            meta_content += "[X.COM / TWITTER]\n"
            meta_content += f"{socials.get('x_post', 'N/A')}\n\n"

            # 3. Threads
            meta_content += "[THREADS]\n"
            meta_content += f"{socials.get('threads_post', 'N/A')}\n\n"
            
            # 4. Instagram
            meta_content += "[INSTAGRAM]\n"
            meta_content += f"{socials.get('instagram_caption', 'N/A')}\n\n"
            
            # 5. TikTok
            meta_content += "[TIKTOK]\n"
            meta_content += f"{socials.get('tiktok_caption', 'N/A')}\n"
            
            time_tag = datetime.now().strftime("%m%d_%H%M")
            meta_path = os.path.join(output_dir, f"metadata_{time_tag}.txt")
            
            with open(meta_path, "w", encoding="utf-8") as f:
                f.write(meta_content)
            print(f"✅ 메타데이터 저장 완료: {meta_path}")

    except json.JSONDecodeError as e:
        print(f"❌ JSON 파싱 오류: {e}")
        print(text[:500])

if __name__ == "__main__":
    generate_story()