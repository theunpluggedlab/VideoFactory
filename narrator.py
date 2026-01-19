import os
import json
import sys
import asyncio
import subprocess
import shutil
import edge_tts
import imageio_ffmpeg
from dotenv import load_dotenv
import time

load_dotenv()
GEMINI_KEYS = []
if os.environ.get("GEMINI_API_KEY"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY"))

VOICE_DB = {
    "en": {"m": "en-US-ChristopherNeural", "f": "en-US-AriaNeural"},
    "ko": {"m": "ko-KR-InJoonNeural", "f": "ko-KR-SunHiNeural"}
}

language = "ko"
if len(sys.argv) > 1: language = sys.argv[1]
gender = "f"
if len(sys.argv) > 2: gender = sys.argv[2]
if language not in VOICE_DB: language = "ko"
selected_edge_voice = VOICE_DB[language][gender]

print(f"🎙️ 성우 설정: 언어={language}, 성별={gender}")
print(f"   👉 [Main] Edge TTS (Microsoft): {selected_edge_voice}")

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

def speed_up_audio(input_file, output_file, speed=1.1):
    try:
        cmd = [
            FFMPEG_EXE, "-y", "-i", input_file, 
            "-filter:a", f"atempo={speed}", 
            "-vn", "-loglevel", "error", output_file
        ]
        startupinfo = None
        if sys.platform == 'win32':
             startupinfo = subprocess.STARTUPINFO()
             startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
        return True
    except Exception as e:
        print(f"      ⚠️ FFmpeg 속도 변환 실패: {e}")
        try: shutil.copy2(input_file, output_file); return True
        except: return False

async def generate_audio_edge(text, output_file):
    try:
        communicate = edge_tts.Communicate(text, selected_edge_voice)
        await communicate.save(output_file)
        return True
    except Exception as e:
        print(f"   ❌ Edge TTS 실패: {e}")
        return False

def main():
    story_path = "story.json"
    audio_dir = "audio"
    if not os.path.exists(story_path):
        print(f"오류: '{story_path}' 없음.")
        sys.exit(1)
    os.makedirs(audio_dir, exist_ok=True)
        
    try:
        with open(story_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        print("❌ story.json 읽기 실패")
        sys.exit(1)

    # [핵심 수정] JSON 구조 유연하게 처리
    scenes = []
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and "scenes" in data[0]:
        scenes = data[0]["scenes"]
    elif isinstance(data, dict) and "scenes" in data:
        scenes = data["scenes"]
    elif isinstance(data, list):
        scenes = data

    print(f"✅ 성우가 녹음할 Scene 개수: {len(scenes)}")
    if len(scenes) == 0:
        print("⚠️ 경고: 녹음할 대본이 없습니다.")
        return

    print(f"=== 성우 에이전트 시작 (Edge TTS Mode) ===")
    failed_count = 0
    
    for i, scene in enumerate(scenes):
        idx = i + 1
        text = scene.get("narration")
        if not text: continue
        clean_text = text.replace("*", "").replace("\"", "").replace("'", "")
        if not clean_text: continue
             
        file_name = f"audio_{idx}.mp3"
        final_path = os.path.join(audio_dir, file_name)
        temp_mp3 = os.path.join(audio_dir, f"temp_{idx}.mp3")
        
        print(f"🎤 [{idx}/{len(scenes)}] 녹음: {clean_text[:20]}...")
        
        if asyncio.run(generate_audio_edge(clean_text, temp_mp3)):
            if speed_up_audio(temp_mp3, final_path, speed=1.15):
                print(f"   ✅ 저장 완료: {file_name}")
            else: failed_count += 1
            if os.path.exists(temp_mp3): os.remove(temp_mp3)
        else:
             print(f"   ❌ 녹음 실패")
             failed_count += 1

    if failed_count > 0: print(f"\n❌ {failed_count}개 실패.")
    else: print("\n=== 모든 녹음 완료 ===")

if __name__ == "__main__":
    main()