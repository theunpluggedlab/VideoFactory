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

# .env 파일 로드
load_dotenv()

# [라이브러리 로드] 구글 최신 SDK 확인
try:
    from google import genai
    from google.genai import types
    HAS_GEMINI_TTS = True
except ImportError:
    print("⚠️ 'google-genai' 라이브러리가 없거나 로드할 수 없습니다.")
    print("   👉 자동으로 Edge TTS (무료) 모드로 전환합니다.")
    HAS_GEMINI_TTS = False

# [핵심] API 키 4개 로드 (환경변수에서 가져옴)
GEMINI_KEYS = []
if os.environ.get("GEMINI_API_KEY"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY"))
if os.environ.get("GEMINI_API_KEY_2"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY_2"))
if os.environ.get("GEMINI_API_KEY_3"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY_3"))
if os.environ.get("GEMINI_API_KEY_4"): GEMINI_KEYS.append(os.environ.get("GEMINI_API_KEY_4"))

# 키가 하나도 없으면 경고
if not GEMINI_KEYS and HAS_GEMINI_TTS:
    print("❌ 경고: .env 파일에서 GEMINI_API_KEY를 찾을 수 없습니다.")

# 전역 변수로 키 인덱스 관리 (순환을 위해)
current_key_index = 0
print(f"🔑 [Narrator] 로드된 Gemini API 키 개수: {len(GEMINI_KEYS)}개")

# 목소리 데이터베이스
VOICE_DB = {
    "en": {
        "m": {"gemini": "Puck", "edge": "en-US-ChristopherNeural"},
        "f": {"gemini": "Aoede", "edge": "en-US-AriaNeural"}
    },
    "ko": {
        "m": {"gemini": "Puck", "edge": "ko-KR-InJoonNeural"},
        "f": {"gemini": "Aoede", "edge": "ko-KR-SunHiNeural"}
    }
}

# 인자 설정 (언어, 성별)
language = "ko"
if len(sys.argv) > 1: language = sys.argv[1]

gender = "f"
if len(sys.argv) > 2: gender = sys.argv[2]

if language not in VOICE_DB: language = "ko"
selected_gemini_voice = VOICE_DB[language][gender]["gemini"]
selected_edge_voice = VOICE_DB[language][gender]["edge"]

print(f"🎙️ 성우 설정: 언어={language}, 성별={gender}")
print(f"   [Primary] Gemini: {selected_gemini_voice}")
print(f"   [Fallback] Edge TTS: {selected_edge_voice}")

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

def speed_up_audio(input_file, output_file, speed=1.2):
    try:
        cmd = [
            FFMPEG_EXE, "-y", 
            "-i", input_file, 
            "-filter:a", f"atempo={speed}", 
            "-vn", 
            "-loglevel", "error",
            output_file
        ]
        startupinfo = None
        if sys.platform == 'win32':
             startupinfo = subprocess.STARTUPINFO()
             startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
        return True
    except Exception as e:
        print(f"      ⚠️ FFmpeg 속도 변환 실패: {e}")
        try:
            shutil.copy2(input_file, output_file)
            return True
        except: return False

def save_pcm_as_wav(pcm_data, filename, sample_rate=24000):
    import wave
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)

def generate_audio_gemini(text, output_file):
    """
    Gemini API 키 4개를 순차적으로 시도합니다.
    429(쿼터) 뿐만 아니라 400(기능 미지원) 에러도 키 문제로 간주하고 넘깁니다.
    """
    if not HAS_GEMINI_TTS or not GEMINI_KEYS: return False
    global current_key_index
    
    # 총 키 개수만큼 시도 (예: 4개면 4번 시도)
    max_attempts = len(GEMINI_KEYS)
    attempts = 0
    
    while attempts < max_attempts:
        current_key = GEMINI_KEYS[current_key_index]
        try:
            print(f"   ⏳ [Gemini] 요청 중... (Key #{current_key_index+1} 사용)")
            client = genai.Client(api_key=current_key)
            
            config = types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=selected_gemini_voice)
                    )
                )
            )
            
            response = client.models.generate_content(
                model="gemini-2.0-flash-exp", 
                contents=text, 
                config=config
            )
            
            all_pcm_data = bytearray()
            if response.parts:
                for part in response.parts:
                    if part.inline_data:
                        all_pcm_data.extend(part.inline_data.data)
            
            if all_pcm_data:
                save_pcm_as_wav(all_pcm_data, output_file)
                print(f"   💾 [Gemini] WAV 생성 성공")
                return True
            else:
                 raise Exception("No audio data received")

        except Exception as e:
            error_str = str(e)
            
            # [수정된 핵심 로직] 429(쿼터), 400(Invalid), 500(서버) 등 모든 에러에 대해 다음 키 시도
            # 특정 키가 오디오 기능을 지원하지 않는 경우(400)도 포함
            is_retryable = False
            if "429" in error_str or "RESOURCE" in error_str or "quota" in error_str.lower():
                is_retryable = True
                print(f"      ⚠️ [Key #{current_key_index+1}] 쿼터 초과! 다음 키로 교체합니다.")
            elif "400" in error_str or "INVALID_ARGUMENT" in error_str:
                is_retryable = True
                print(f"      ⚠️ [Key #{current_key_index+1}] 오디오 미지원 키/모델(400). 다음 키로 교체합니다.")
            elif "500" in error_str or "503" in error_str:
                is_retryable = True
                print(f"      ⚠️ [Key #{current_key_index+1}] 구글 서버 일시 오류(5xx). 다음 키로 교체합니다.")
            
            if is_retryable:
                current_key_index = (current_key_index + 1) % len(GEMINI_KEYS)
                attempts += 1
                time.sleep(1) 
                continue
            else:
                print(f"      ❌ [Gemini] 치명적 오류: {error_str}")
                return False 
                
    print(f"      ❌ 모든 Gemini 키({len(GEMINI_KEYS)}개)가 실패했습니다.")
    return False

async def generate_audio_edge(text, output_file):
    try:
        print(f"   ⏳ [Edge TTS] 요청 중...")
        communicate = edge_tts.Communicate(text, selected_edge_voice)
        await communicate.save(output_file)
        print(f"   ✅ [Edge TTS] 성공")
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
        
    with open(story_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    story_content = data[0] if isinstance(data, list) else data
    scenes = story_content.get("scenes", [])
    
    print(f"=== 성우 에이전트 시작 (4-Key Full Rotation) ===")
    
    failed_count = 0
    
    for i, scene in enumerate(scenes):
        idx = i + 1
        text = scene.get("narration")
        if not text: continue
            
        clean_text = text.replace("*", "") 
        if not clean_text: continue
             
        file_name = f"audio_{idx}.mp3"
        final_path = os.path.join(audio_dir, file_name)
        
        temp_wav = os.path.join(audio_dir, f"temp_{idx}.wav")
        temp_mp3 = os.path.join(audio_dir, f"temp_{idx}.mp3")
        
        print(f"\n🎤 [{idx}/{len(scenes)}] 녹음: {clean_text[:20]}...")
        
        # 1. Gemini 시도 (키 4개 순환)
        raw_source_path = None
        if generate_audio_gemini(clean_text, temp_wav):
            raw_source_path = temp_wav
        
        # 2. 실패시 Edge TTS (최후의 보루)
        if not raw_source_path:
            print("   👉 Edge TTS로 전환...")
            if asyncio.run(generate_audio_edge(clean_text, temp_mp3)):
                raw_source_path = temp_mp3
            
        # 3. 속도 변환 및 파일 정리
        if raw_source_path:
            if speed_up_audio(raw_source_path, final_path, speed=1.2):
                pass
            else:
                failed_count += 1
            
            if os.path.exists(temp_wav): os.remove(temp_wav)
            if os.path.exists(temp_mp3): os.remove(temp_mp3)
        else:
             print(f"   ❌ 녹음 최종 실패")
             failed_count += 1

    if failed_count > 0:
        print(f"\n❌ {failed_count}개 실패.")
        sys.exit(1)
    else:
        print("\n=== 녹음 완료 ===")

if __name__ == "__main__":
    main()