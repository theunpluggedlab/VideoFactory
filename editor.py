import os
import json
import sys
import traceback
import re
import numpy as np
from PIL import Image, ImageFont, ImageDraw
import shutil
from datetime import datetime

# [핵심 수정] Pillow 최신 버전 호환성 패치
# Pillow 10.0.0부터 ANTIALIAS가 삭제되었으므로, 이를 LANCZOS로 매핑해줍니다.
if not hasattr(Image, 'ANTIALIAS'):
    Image.ANTIALIAS = Image.LANCZOS

# MoviePy Import (v1.0.3 호환)
try:
    from moviepy.editor import *
    from moviepy.video.tools.subtitles import SubtitlesClip
except ImportError:
    print("❌ moviepy 라이브러리를 찾을 수 없습니다.")
    print("   👉 설치 방법: pip install moviepy")
    sys.exit(1)

# 폰트 경로 정의 (Windows 기준)
FONT_EN = "C:/Windows/Fonts/arialbd.ttf"
FONT_KO = "C:/Windows/Fonts/malgunbd.ttf"
FONT_DEFAULT = "arial.ttf"

def get_font_path(text):
    if re.search("[가-힣]", text):
        if os.path.exists(FONT_KO): return FONT_KO
        if os.path.exists("C:/Windows/Fonts/malgun.ttf"): return "C:/Windows/Fonts/malgun.ttf"
    if os.path.exists(FONT_EN): return FONT_EN
    return FONT_DEFAULT

def create_highlighted_text_clip(text, fontsize, color='white', highlight_color='yellow', 
                               stroke_color='black', stroke_width=2, 
                               max_width=680, align='center', is_title=False):
    """Pillow를 사용하여 텍스트 이미지 클립 생성"""
    tokens = []
    try:
        if sys.platform == 'win32': text = text.encode('gbk', 'ignore').decode('gbk')
    except: pass

    parts = text.split('*')
    for i, part in enumerate(parts):
        c = highlight_color if i % 2 == 1 else color
        words = part.split()
        for word in words:
            tokens.append({'text': word, 'color': c})

    font_path = get_font_path(text)
    try: font = ImageFont.truetype(font_path, fontsize)
    except: font = ImageFont.load_default()

    dummy_draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    space_w = dummy_draw.textbbox((0, 0), " ", font=font)[2]
    
    lines = []
    current_line = []
    current_w = 0
    for token in tokens:
        bbox = dummy_draw.textbbox((0, 0), token['text'], font=font)
        word_w = bbox[2] - bbox[0]
        if current_line and (current_w + word_w > max_width):
            lines.append(current_line)
            current_line = [token]
            current_w = word_w + space_w
        else:
            current_line.append(token)
            current_w += word_w + space_w
    if current_line: lines.append(current_line)

    line_height = int(fontsize * 1.4)
    total_height = len(lines) * line_height + 20
    canvas_w = max_width + 40
    img = Image.new('RGBA', (canvas_w, total_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    y = 10
    for line_tokens in lines:
        line_w = 0
        for t in line_tokens:
            w = draw.textbbox((0, 0), t['text'], font=font)[2] - draw.textbbox((0, 0), t['text'], font=font)[0]
            line_w += w + space_w
        line_w -= space_w
        x = (canvas_w - line_w) // 2 if align == 'center' else 10
            
        for t in line_tokens:
            txt = t['text']; col = t['color']
            for dx in range(-stroke_width, stroke_width+1):
                for dy in range(-stroke_width, stroke_width+1):
                    if dx!=0 or dy!=0: draw.text((x+dx, y+dy), txt, font=font, fill=stroke_color)
            draw.text((x, y), txt, font=font, fill=col)
            w = draw.textbbox((0, 0), txt, font=font)[2] - draw.textbbox((0, 0), txt, font=font)[0]
            x += w + space_w
        y += line_height
        
    return ImageClip(np.array(img))

def create_source_label(text, font_path):
    try: font = ImageFont.truetype(font_path, 20)
    except: font = ImageFont.load_default()
    dummy_draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    bbox = dummy_draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0] + 20
    h = bbox[3] - bbox[1] + 10
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x, y = 10, 0
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            draw.text((x+dx, y+dy), text, font=font, fill='black')
    draw.text((x, y), text, font=font, fill='white')
    return ImageClip(np.array(img))

def create_video():
    mode = "video"
    if len(sys.argv) > 1: mode = sys.argv[1]

    is_shorts = "shorts" in mode
    is_news = "news" in mode
    
    story_path = "story.json"
    image_dir = "images"
    audio_dir = "audio"
    intro_path = "assets/intro.mp4"
    outro_path = "assets/outro.mp4"
    
    if not os.path.exists(story_path):
        print("❌ 오류: story.json 파일이 없습니다.")
        return

    with open(story_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    story_content = data[0] if isinstance(data, list) else data
            title_text = story_content.get("title", "News Briefing")
    scenes = story_content.get("scenes", [])
    
    image_sources = {}
    sources_path = os.path.join(image_dir, "sources.json")
    if os.path.exists(sources_path):
        try:
            with open(sources_path, "r", encoding="utf-8") as f:
                image_sources = json.load(f)
        except: pass

    print(f"=== 편집(Editor) 시작 (Mode: {mode}) ===")
    
    # 3단 분리 저장소 (Intro / Body / Outro)
    intro_clip_final = None
    outro_clip_final = None
    body_clips = []

    final_size = (720, 1280) if is_shorts else (1280, 720)

    for i, scene in enumerate(scenes):
        idx = i + 1
        img_path = os.path.join(image_dir, f"image_{idx}.png")
        aud_path = os.path.join(audio_dir, f"audio_{idx}.mp3")
        
        if not os.path.exists(aud_path):
            print(f"⚠️ 오디오 누락 (Scene {idx}), 건너뜀.")
            continue

        print(f"🎬 Scene {idx} 합성 중...")
        
        audio_clip = AudioFileClip(aud_path)
        duration = audio_clip.duration
        
        visual_clip = None
        is_video_asset = False
        is_intro_scene = (i == 0 and is_shorts and is_news)
        is_outro_scene = (i == len(scenes) - 1 and is_shorts and is_news)

        # ----------------------------------------------------------------
        # 1. 비디오/이미지 소스 결정
        # ----------------------------------------------------------------
        if is_intro_scene and os.path.exists(intro_path):
            print("   👉 Intro 영상 적용 (Looping)")
            vid = VideoFileClip(intro_path)
            # Intro: 오디오 제거 후 루핑 (나래이션 오디오가 덮일 예정)
            visual_clip = vid.without_audio().loop(duration=duration)
            is_video_asset = True

        elif is_outro_scene and os.path.exists(outro_path):
            print("   👉 Outro 영상 적용 (Trimming)")
            vid = VideoFileClip(outro_path)
            # Outro: 오디오 제거
            vid = vid.without_audio()
            
            if vid.duration > duration:
                visual_clip = vid.subclip(0, duration)
            else:
                visual_clip = vid.set_duration(duration)
            is_video_asset = True
        
        else:
            if os.path.exists(img_path):
                visual_clip = ImageClip(img_path).set_duration(duration)
            else:
                print(f"⚠️ 이미지 누락 (Scene {idx})")
                continue

        # ----------------------------------------------------------------
        # 2. 레이아웃 합성
        # ----------------------------------------------------------------
        layers = []
        
        if is_shorts:
            # 검은 배경
            black_bg = ColorClip(size=final_size, color=(0, 0, 0)).set_duration(duration)
            layers.append(black_bg)
            
            # 리사이즈 및 중앙 정렬 (Resize 에러 해결: 패치 적용됨)
            resized_visual = visual_clip.resize(width=720)
            centered_visual = resized_visual.set_position("center")
            layers.append(centered_visual)
            
        else:
            # Video 모드
            resized_visual = visual_clip.resize(width=1280)
            layers.append(resized_visual)

        # 출처 표시 (이미지인 경우에만, Intro/Outro 제외)
        if not is_video_asset:
            img_filename = f"image_{idx}.png"
            if img_filename in image_sources:
                source_text = f"Source: {image_sources[img_filename]}"
                source_clip = create_source_label(source_text, FONT_EN)
                source_y = 50 if is_shorts else 20
                source_clip = source_clip.set_position(("right", source_y)).set_duration(duration)
                layers.append(source_clip)

        # 자막 표시 (모든 Scene 적용 - Intro/Outro 포함)
        if is_shorts:
            narration = scene.get("narration", "")
            if narration:
                txt_clip = create_highlighted_text_clip(
                    narration, fontsize=45, color='white', highlight_color='yellow', 
                    max_width=650
                )
                txt_clip = txt_clip.set_position(("center", 950)).set_duration(duration)
                layers.append(txt_clip)

        # 개별 Scene 최종 합성 (나래이션 오디오 포함)
        scene_composite = CompositeVideoClip(layers, size=final_size).set_audio(audio_clip)

        # ----------------------------------------------------------------
        # 3. 클립 분류 (Intro / Body / Outro)
        # ----------------------------------------------------------------
        if is_intro_scene:
            intro_clip_final = scene_composite
        elif is_outro_scene:
            outro_clip_final = scene_composite
        else:
            body_clips.append(scene_composite)

    if not body_clips:
        print("❌ 본문 클립이 생성되지 않았습니다.")
        return

    # ----------------------------------------------------------------
    # 4. 최종 연결 (Concatenate)
    # ----------------------------------------------------------------
    print("🎞️ 클립 병합 및 타이틀 적용 중...")
    
    # [1] 본문 병합
    body_concat = concatenate_videoclips(body_clips, method="compose")
    
    # [2] 본문에만 타이틀 오버레이 적용 (Intro/Outro 침범 방지)
    if is_shorts and is_news:
        print("   📝 본문에만 타이틀 적용")
        title_clip = create_highlighted_text_clip(
            title_text, fontsize=50, color='white', highlight_color='#00ff00',
            is_title=True, max_width=680
        )
        title_clip = title_clip.set_position(("center", 100)).set_duration(body_concat.duration)
        body_concat = CompositeVideoClip([body_concat, title_clip], size=final_size)
    
    # [3] 최종 시퀀스 조립: Intro -> Body -> Outro
    final_sequence = []
    
    if intro_clip_final:
        final_sequence.append(intro_clip_final)
        
    final_sequence.append(body_concat)
    
    if outro_clip_final:
        final_sequence.append(outro_clip_final)

    final_clip = concatenate_videoclips(final_sequence, method="compose")

    # 저장
    output_dir = "results"
    os.makedirs(output_dir, exist_ok=True)
    
    time_tag = datetime.now().strftime("%m%d_%H%M")
    base_name = "final_shorts" if is_shorts else "final_video"
    
    filename_timestamp = f"{base_name}_{time_tag}.mp4"
    filename_latest = f"{base_name}.mp4"
    
    output_path = os.path.join(output_dir, filename_timestamp)
    latest_path = os.path.join(output_dir, filename_latest)
    
    print(f"🚀 렌더링 시작: {output_path}")
    
    final_clip.write_videofile(
        output_path, 
        fps=24, 
        codec="libx264", 
        audio_codec="aac",
        threads=4,
        logger="bar"
    )
    
    shutil.copy2(output_path, latest_path)
    print(f"✨ 편집 완료! (저장: {output_path})")

if __name__ == "__main__":
    create_video()