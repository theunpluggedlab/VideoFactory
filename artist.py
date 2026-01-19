import os
import json
import time
from dotenv import load_dotenv
import google.generativeai as genai
from PIL import Image, ImageDraw
import io
import requests
import sys
from urllib.parse import urlparse
import random

# 1. 설정 및 초기화
load_dotenv()
SERPER_API_KEY = os.getenv("SERPER_API_KEY")

# API 키 5개 로드
GEMINI_KEYS = []
if os.environ.get("GEMINI_API_KEY"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY"))
if os.environ.get("GEMINI_API_KEY_2"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY_2"))
if os.environ.get("GEMINI_API_KEY_3"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY_3"))
if os.environ.get("GEMINI_API_KEY_4"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY_4"))
if os.environ.get("GEMINI_API_KEY_5"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY_5"))

if not GEMINI_KEYS:
    print("FATAL: .env 파일에서 GEMINI_API_KEY를 찾을 수 없습니다.")
    sys.exit(1)

current_key_index = 0
print(f"🔑 [Artist] 로드된 Gemini API 키 개수: {len(GEMINI_KEYS)}개")

OUTPUT_DIR = "images"
ASSETS_DIR = "assets"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

MODEL_NAME = "gemini-2.0-flash" 

MAJOR_NEWS_SITES = [
    "cnn.com", "foxnews.com", "usatoday.com", "reuters.com", "apnews.com",
    "bbc.com", "abcnews.go.com", "cbsnews.com", "nbcnews.com", "nytimes.com",
    "washingtonpost.com", "wsj.com", "bloomberg.com", "npr.org", "theguardian.com"
]

def crop_center(pil_img, crop_width, crop_height):
    img_width, img_height = pil_img.size
    return pil_img.crop(((img_width - crop_width) // 2,
                         (img_height - crop_height) // 2,
                         (img_width + crop_width) // 2,
                         (img_height + crop_height) // 2))

def crop_to_aspect_ratio(pil_img, target_ratio):
    img_width, img_height = pil_img.size
    img_ratio = img_width / img_height
    if img_ratio > target_ratio:
        new_width = int(img_height * target_ratio)
        new_height = img_height
    else:
        new_width = img_width
        new_height = int(img_width / target_ratio)
    return crop_center(pil_img, new_width, new_height)

def process_and_save_image(pil_img, save_path, target_ratio):
    try:
        cropped_img = crop_to_aspect_ratio(pil_img, target_ratio)
        min_dim = 1080 
        w, h = cropped_img.size
        scale = max(min_dim/w, min_dim/h)
        if scale > 1:
             new_size = (int(w*scale), int(h*scale))
             cropped_img = cropped_img.resize(new_size, Image.LANCZOS)
        cropped_img.save(save_path, "PNG")
        return True
    except Exception as e:
        print(f"⚠️ 이미지 가공 실패: {e}")
        return False

def is_valid_image(file_path):
    try:
        if not os.path.exists(file_path): return False
        if os.path.getsize(file_path) < 20000: return False 
        with Image.open(file_path) as img:
            w, h = img.size
            if w < 800 and h < 800: return False
        return True
    except: return False

def is_blacklisted(url):
    url_lower = url.lower()
    social_blacklist = ['instagram.com', 'facebook.com', 'tiktok.com', 'x.com', 'twitter.com', 'pinterest.com', 'linkedin.com']
    stock_blacklist = ['gettyimages', 'shutterstock', 'istockphoto', 'stock.adobe', 'alamy', 'dreamstime', '123rf', 'depositphotos', 'pond5', 'vectors']
    for domain in social_blacklist + stock_blacklist:
        if domain in url_lower: return True
    return False

def create_fallback_image(file_name, target_ratio):
    save_path = os.path.join(OUTPUT_DIR, file_name)
    default_img_path = os.path.join(ASSETS_DIR, "default_news.png")
    
    if os.path.exists(default_img_path):
        try:
            print(f"   🏞️ 기본 이미지(Fallback) 사용.")
            with Image.open(default_img_path) as img:
                if img.mode in ("RGBA", "P"): img = img.convert("RGB")
                process_and_save_image(img, save_path, target_ratio)
            return
        except: pass

    print(f"   🎨 비상용 그래픽 생성.")
    w = 1080
    h = int(w / target_ratio)
    img = Image.new('RGB', (w, h), color=(20, 30, 60)) 
    draw = ImageDraw.Draw(img)
    draw.line([(0, h*0.8), (w, h*0.8)], fill=(40, 50, 80), width=10)
    process_and_save_image(img, save_path, target_ratio)

def search_google_images(query, num=30): 
    url = "https://google.serper.dev/images"
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    payload = json.dumps({"q": query, "num": num, "gl": "us", "hl": "en"})
    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        if response.status_code != 200: return []
        return response.json().get('images', [])
    except: return []

def download_and_process_image(image_url, file_name, target_ratio):
    save_path = os.path.join(OUTPUT_DIR, file_name)
    try:
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        ]
        headers = {'User-Agent': random.choice(user_agents)}
        response = requests.get(image_url, headers=headers, timeout=8)
        response.raise_for_status()
        if len(response.content) < 20000: raise Exception("File too small")
        img = Image.open(io.BytesIO(response.content))
        w, h = img.size
        if w < 800 and h < 800: raise Exception(f"Low Resolution ({w}x{h} < 800px)")
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        return process_and_save_image(img, save_path, target_ratio)
    except Exception as e: return False

def search_with_fallback(base_prompt, idx):
    selected_sites = random.sample(MAJOR_NEWS_SITES, 6)
    site_operators = " OR ".join([f"site:{site}" for site in selected_sites])
    forced_query = f"{base_prompt} {site_operators}"
    print(f"   🔍 [Scene {idx}] 1차 검색: '{forced_query[:60]}...'")
    results = search_google_images(forced_query, num=30)
    if results: return results
    
    print(f"   🔄 [Scene {idx}] 2차 검색: '{base_prompt}'")
    results = search_google_images(base_prompt, num=30)
    return results

def download_best_available_image(results, file_name, target_ratio):
    for item in results:
        url = item.get('imageUrl')
        if not url or is_blacklisted(url): continue
        if download_and_process_image(url, file_name, target_ratio):
            print(f"      ✅ 원본 다운로드 성공")
            return url
    for item in results:
        thumb = item.get('thumbnailUrl')
        if not thumb: continue
        if download_and_process_image(thumb, file_name, target_ratio):
            print(f"      ✅ 썸네일 다운로드 성공")
            return thumb
    return None

def generate_image(prompt, file_name):
    global current_key_index
    print(f"🎨 AI 그리기 시도... ({prompt[:20]}...)")
    attempts = 0
    max_attempts = len(GEMINI_KEYS) * 3 
    
    while attempts < max_attempts:
        current_key = GEMINI_KEYS[current_key_index]
        try:
            genai.configure(api_key=current_key) 
            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(prompt) 
            if hasattr(response, 'parts') and response.parts and response.parts[0].inline_data:
                 image_data = response.parts[0].inline_data.data
                 img = Image.open(io.BytesIO(image_data))
                 save_path = os.path.join(OUTPUT_DIR, file_name)
                 img.save(save_path)
                 return True
            return False 
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                print(f"      ⚠️ [Key #{current_key_index+1}] 쿼터 초과! 10초 대기...")
                time.sleep(10)
                current_key_index = (current_key_index + 1) % len(GEMINI_KEYS)
                attempts += 1
                continue
            else:
                print(f"      ❌ 그리기 오류: {e}")
                attempts += 1
                current_key_index = (current_key_index + 1) % len(GEMINI_KEYS)
                continue
    return False

# ---------------------------
# 메인 함수
# ---------------------------
def main():
    mode = "video"
    if len(sys.argv) > 1: mode = sys.argv[1]
        
    is_shorts = "shorts" in mode
    is_news = "news" in mode
    target_ratio = (9/16) if is_shorts else (16/9)
    if is_news and is_shorts: target_ratio = 4/3 

    story_path = "story.json"
    if not os.path.exists(story_path):
        print(f"오류: {story_path} 없음.")
        return
    
    try:
        with open(story_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        print("❌ JSON 읽기 실패")
        return

    # [핵심 수정] JSON 구조 유연하게 처리 (리스트 래핑 해제)
    scenes = []
    # 1. 리스트 안에 딕셔너리가 들어있는 경우 (Writer가 감싸서 줄 때)
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and "scenes" in data[0]:
        scenes = data[0]["scenes"]
    # 2. 그냥 딕셔너리인 경우
    elif isinstance(data, dict) and "scenes" in data:
        scenes = data["scenes"]
    # 3. 리스트 자체가 씬 목록인 경우
    elif isinstance(data, list):
        scenes = data

    print(f"✅ 화가가 작업할 Scene 개수: {len(scenes)}")
    if len(scenes) == 0:
        print("⚠️ 경고: 작업할 Scene이 없습니다.")
        return

    print(f"=== 화가 에이전트 시작 (High Persistence Mode) ===")
    
    image_sources = {}
    article_images = []
    
    if mode == "url_news_shorts" and os.path.exists("article_cache.json"):
        try:
            with open("article_cache.json", "r", encoding="utf-8") as f:
                article_images = json.load(f).get("images", [])
        except: pass

    for i, scene in enumerate(scenes):
        idx = i + 1
        base_prompt = scene.get("image_prompt")
        
        if is_shorts and is_news and i == 0 and os.path.exists("assets/intro.mp4"):
            print(f"   ⏩ Scene {idx} (Intro): Skip")
            continue
        if is_shorts and is_news and i == len(scenes) - 1 and os.path.exists("assets/outro.mp4"):
            print(f"   ⏩ Scene {idx} (Outro): Skip")
            continue

        if not base_prompt: continue
        
        file_name = f"image_{idx}.png"
        success = False
        
        if is_news:
            if mode == "url_news_shorts" and article_images and i < len(article_images):
                img_url = article_images[i]
                if not is_blacklisted(img_url):
                    print(f"   [기사 사진 시도] Scene {idx}")
                    if download_and_process_image(img_url, file_name, target_ratio):
                        if is_valid_image(os.path.join(OUTPUT_DIR, file_name)):
                            image_sources[file_name] = urlparse(img_url).netloc
                            success = True
            
            if not success:
                search_results = search_with_fallback(base_prompt, idx)
                if search_results:
                    final_url = download_best_available_image(search_results, file_name, target_ratio)
                    if final_url:
                        image_sources[file_name] = urlparse(final_url).netloc
                        success = True
            
            if not success:
                print(f"   ⚠️ 검색 전멸. AI 생성 시도.")
                if generate_image(f"News photo of {base_prompt}, realistic, 4k", file_name):
                    try:
                        with Image.open(os.path.join(OUTPUT_DIR, file_name)) as img:
                            process_and_save_image(img, os.path.join(OUTPUT_DIR, file_name), target_ratio)
                        success = True
                    except: pass
        else: 
            prompt = f"{base_prompt}, cinematic lighting, high quality, 4k, detailed"
            if generate_image(prompt, file_name):
                try:
                    with Image.open(os.path.join(OUTPUT_DIR, file_name)) as img:
                        process_and_save_image(img, os.path.join(OUTPUT_DIR, file_name), target_ratio)
                    success = True
                except: pass

        if not success:
            create_fallback_image(file_name, target_ratio)
        
        time.sleep(1) 

    if image_sources:
        with open(os.path.join(OUTPUT_DIR, "sources.json"), "w", encoding="utf-8") as f:
            json.dump(image_sources, f, indent=2, ensure_ascii=False)

    print("\n=== 모든 작업 완료 ===")

if __name__ == "__main__":
    main()