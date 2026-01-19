import subprocess
import sys
import json
import os

# newspaper3k 라이브러리 체크
try:
    from newspaper import Article, Config
except ImportError:
    pass

PYTHON_EXE = sys.executable 

def run_step(step_name, script_name, args=[]):
    print(f"\n{'='*50}")
    print(f"🎬 [Step: {step_name}] 시작합니다...")
    print(f"{'='*50}\n")
    
    # 환경 변수 설정 (버퍼링 없이 즉시 출력)
    current_env = os.environ.copy()
    current_env["PYTHONUNBUFFERED"] = "1"
    
    command = [PYTHON_EXE, script_name] + args
    
    try:
        subprocess.run(command, check=True, env=current_env)
        print(f"\n✅ [Step: {step_name}] 완료!\n")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ [Step: {step_name}] 에러 발생! (Exit Code: {e.returncode})")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)

def main():
    print(f"{'='*60}")
    print("🎥 AI Video Factory - 총괄 감독 시스템 가동 🎥")
    print(f"{'='*60}\n")

    try:
        print("[제작 모드 선택]", flush=True)
        print("1. 창작 비디오 (16:9 가로)", flush=True)
        print("2. 창작 쇼츠 (9:16 세로)", flush=True)
        print("3. 뉴스 비디오 (16:9 가로)", flush=True)
        print("4. 뉴스 쇼츠 (9:16 세로)", flush=True)
        print("5. URL 뉴스 쇼츠 (News URL to Shorts)", flush=True)
        
        choice = input("👉 번호를 입력하세요 (기본값: 1): ").strip()

        mode = "video"
        topic = "자유 주제"

        if choice == "2":
            mode = "shorts"
            print("📱 '창작 쇼츠' 모드 선택됨.")
        elif choice == "3":
            mode = "news_video"
            topic = "Today's Top News"
            print("📰 '뉴스 비디오' 모드 선택됨.")
        elif choice == "4":
            mode = "news_shorts"
            topic = "Today's Top News"
            print("📰📱 '뉴스 쇼츠' 모드 선택됨.")
        elif choice == "5":
            mode = "url_news_shorts"
            topic = "News URL"
            print("🔗 'URL 뉴스 쇼츠' 모드 선택됨.")
            
            url = input("\n🔗 뉴스 기사 URL을 입력하세요: ").strip()
            if not url: sys.exit(1)
                
            print(f"🕷️ 기사 분석 중... ({url})")
            
            # [수정] 크롤링 시도 -> 실패 시 수동 입력 로직으로 연결
            try:
                config = Config()
                # 봇 차단 회피용 헤더 강화
                config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                config.request_timeout = 10
                
                article = Article(url, config=config)
                article.download()
                article.parse()
                
                if not article.text or len(article.text) < 50:
                    raise Exception("본문 추출 실패 (내용 없음)")
                
                images = list(article.images) if article.images else []
                article_data = {"title": article.title, "text": article.text, "images": images}
                
                with open("article_cache.json", "w", encoding="utf-8") as f:
                    json.dump(article_data, f, ensure_ascii=False, indent=2)
                print("✅ 기사 데이터 저장 완료 (article_cache.json)")
                
            except Exception as e:
                print(f"\n❌ 자동 수집 실패 ({e})")
                print("⚠️ 보안이 강력한 사이트거나 URL 오류입니다. 수동 입력 모드로 전환합니다.")
                print("-" * 40)
                
                manual_title = input("📝 기사 제목을 입력하세요: ").strip()
                if not manual_title:
                    print("❌ 제목이 없습니다. 종료합니다.")
                    sys.exit(1)
                    
                print("📝 기사 본문을 입력하세요 (복사 후 붙여넣기, 입력 끝나면 Enter 두 번):")
                lines = []
                while True:
                    line = input()
                    if not line: break
                    lines.append(line)
                manual_text = "\n".join(lines)
                
                if len(manual_text) < 10:
                    print("❌ 내용이 너무 짧습니다. 종료합니다.")
                    sys.exit(1)
                    
                article_data = {
                    "title": manual_title,
                    "text": manual_text,
                    "images": [] 
                }
                with open("article_cache.json", "w", encoding="utf-8") as f:
                    json.dump(article_data, f, ensure_ascii=False, indent=2)
                print("✅ 수동 데이터 저장 완료.")

        else:
            mode = "video"
            print("📺 '창작 비디오' 모드 선택됨.")

        if mode in ["video", "shorts"]:
            user_topic = input("\n💡 영상 주제를 입력하세요: ").strip()
            if user_topic: topic = user_topic
            
        lang_input = input("\n🗣️ 언어 선택 (1: 한국어, 2: 영어): ").strip()
        language = "en" if lang_input == "2" else "ko"

        gender_input = input("\n🎙️ 성우 성별 (1: 여성, 2: 남성): ").strip()
        gender = "m" if gender_input == "2" else "f"

    except KeyboardInterrupt:
        sys.exit(0)

    # 파이프라인 실행
    run_step("작가 (Writer)", "writer.py", [topic, mode, language])
    run_step("화가 (Artist)", "artist.py", [mode])
    run_step("성우 (Narrator)", "narrator.py", [language, gender])
    run_step("편집 (Editor)", "editor.py", [mode])

    print(f"{'='*60}")
    print("🎉 모든 작업 완료!")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()