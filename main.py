import os
import sys
import subprocess
import json
from newspaper import Article

def get_user_input(prompt):
    try:
        return input(prompt).strip()
    except UnicodeDecodeError:
        return sys.stdin.readline().strip()

def run_step(script_name, args=[]):
    """파이썬 스크립트 실행 헬퍼 함수"""
    print(f"\n==================================================")
    print(f"🎬 [Step: {script_name}] 시작합니다...")
    print(f"==================================================\n")
    
    cmd = [sys.executable, script_name] + args
    try:
        subprocess.run(cmd, check=True)
        print(f"\n✅ [Step: {script_name}] 완료!")
        return True
    except subprocess.CalledProcessError:
        print(f"\n❌ [Step: {script_name}] 에러 발생! (Exit Code: 1)")
        return False

def crawl_url_and_save(url):
    print(f"🔗 URL 크롤링 시작: {url}")
    try:
        article = Article(url)
        article.download()
        article.parse()
        
        data = {
            "title": article.title,
            "text": article.text,
            "images": list(article.images),
            "top_image": article.top_image,
            "url": url
        }
        
        with open("article_cache.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"✅ 기사 추출 완료: {article.title[:30]}...")
        return True
    except Exception as e:
        print(f"❌ 크롤링 실패: {e}")
        return False

def main():
    while True:
        print("\n========================================")
        print("🎥 VideoFactory: AI 영상 제작 스튜디오")
        print("========================================")
        print("1. 🧞‍♂️ 창작 영상 (일반)")
        print("2. 🧞‍♂️ 창작 쇼츠 (Shorts)")
        print("3. 📰 뉴스 영상 (일반 - 주제 검색)")
        print("4. 📰 뉴스 쇼츠 (Shorts - 주제 검색)")
        print("5. 🔗 뉴스 URL 쇼츠 (기사 링크 변환)")
        print("q. 종료")
        print("----------------------------------------")
        
        choice = get_user_input("메뉴를 선택하세요 (1-5/q): ")
        
        if choice.lower() == 'q':
            print("👋 프로그램을 종료합니다.")
            break

        topic = ""
        mode = "video"
        language = "ko"
        
        # ------------------------------------
        # 메뉴별 설정
        # ------------------------------------
        if choice == '1':
            mode = "video"
            topic = get_user_input("주제를 입력하세요 (예: 2050년의 서울): ")
            
        elif choice == '2':
            mode = "shorts"
            topic = get_user_input("주제를 입력하세요 (예: 아기 고양이의 모험): ")
            
        elif choice == '3':
            mode = "news_video"
            topic = get_user_input("검색할 뉴스 키워드 (Enter = Today's Top News): ")
            if not topic: topic = "Today's Top News"
            
        elif choice == '4':
            mode = "news_shorts"
            topic = get_user_input("검색할 뉴스 키워드 (Enter = Today's Top News): ")
            if not topic: topic = "Today's Top News"
            
        elif choice == '5':
            mode = "url_news_shorts"
            url = get_user_input("기사 URL을 붙여넣으세요: ")
            if not url.startswith("http"):
                print("⚠️ 올바른 URL이 아닙니다.")
                continue
            if not crawl_url_and_save(url):
                continue
            topic = "URL_ARTICLE"
            
        else:
            print("⚠️ 잘못된 입력입니다.")
            continue

        # ------------------------------------
        # [수정] 언어 선택 (1: 한국어, 2: 영어)
        # ------------------------------------
        print("\n🌐 언어 선택")
        print("1. 한국어 (Korean) [기본]")
        print("2. 영어 (English)")
        lang_choice = get_user_input("선택 (1/2): ")
        
        if lang_choice == '2':
            language = "en"
        else:
            language = "ko"

        # ------------------------------------
        # [수정] 성우 성별 선택 (1: 여성, 2: 남성)
        # ------------------------------------
        print("\n🎙️ 성우 목소리 선택")
        print("1. 여성 (Female) [기본]")
        print("2. 남성 (Male)")
        gender_choice = get_user_input("선택 (1/2): ")
        
        gender = "m" if gender_choice == '2' else "f"

        print(f"\n🚀 작업 시작! [Mode: {mode} | Topic: {topic[:30]}... | Lang: {language} | Voice: {gender}]")

        # 파이프라인 실행
        if not run_step("writer.py", [topic, mode, language]): continue
        if not run_step("artist.py", [mode]): continue
        if not run_step("narrator.py", [language, gender]): continue
        if not run_step("editor.py", [mode]): continue
        
        print("\n✨ 모든 작업이 성공적으로 완료되었습니다!")

if __name__ == "__main__":
    main()