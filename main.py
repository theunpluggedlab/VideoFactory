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
        # 실시간 로그 출력을 위해 check=True 사용
        subprocess.run(cmd, check=True)
        print(f"\n✅ [Step: {script_name}] 완료!")
        return True
    except subprocess.CalledProcessError:
        print(f"\n❌ [Step: {script_name}] 에러 발생! (Exit Code: 1)")
        return False

def crawl_url_and_save(url):
    """URL에서 기사 본문과 이미지를 추출하여 저장"""
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
        
        # 캐시 파일로 저장 (Writer와 Artist가 읽을 수 있게)
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
        mode = "video"       # 기본값
        language = "ko"      # 기본값

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
            topic = get_user_input("검색할 뉴스 키워드 (Enter치면 'Today's Top News'): ")
            if not topic: topic = "Today's Top News"
            
        elif choice == '4':
            mode = "news_shorts"
            topic = get_user_input("검색할 뉴스 키워드 (Enter치면 'Today's Top News'): ")
            if not topic: topic = "Today's Top News"
            
        elif choice == '5':
            mode = "url_news_shorts"
            url = get_user_input("기사 URL을 붙여넣으세요: ")
            if not url.startswith("http"):
                print("⚠️ 올바른 URL이 아닙니다.")
                continue
            
            # 1. URL 크롤링 선행
            if not crawl_url_and_save(url):
                continue
            topic = "URL_ARTICLE" # Writer가 캐시파일을 읽도록 유도
            
        else:
            print("⚠️ 잘못된 입력입니다.")
            continue

        # 언어 설정 (공통)
        lang_input = get_user_input("언어 선택 (Enter=한국어, en=영어): ")
        if lang_input.lower() == "en": language = "en"

        # 성우 성별 (공통)
        gender_input = get_user_input("성우 성별 (Enter=여성, m=남성): ")
        gender = "m" if gender_input.lower() == "m" else "f"

        print(f"\n🚀 작업 시작! [Mode: {mode} | Topic: {topic} | Lang: {language}]")

        # ==================================================
        # 파이프라인 실행
        # ==================================================
        
        # 1. Writer (대본 작성)
        # 인자: [주제] [모드] [언어]
        if not run_step("writer.py", [topic, mode, language]): continue
        
        # 2. Artist (이미지 생성/검색)
        # 인자: [모드]
        if not run_step("artist.py", [mode]): continue
        
        # 3. Narrator (더빙)
        # 인자: [언어] [성별]
        if not run_step("narrator.py", [language, gender]): continue
        
        # 4. Editor (편집)
        # 인자: [모드]
        if not run_step("editor.py", [mode]): continue
        
        print("\n✨ 모든 작업이 성공적으로 완료되었습니다!")

if __name__ == "__main__":
    main()