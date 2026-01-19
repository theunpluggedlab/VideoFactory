import os
import json
import sys
import traceback
import re
import numpy as np
from PIL import Image, ImageFont, ImageDraw
import shutil
from datetime import datetime

# MoviePy Import
try:
    from moviepy import *
    from moviepy.video.tools.subtitles import SubtitlesClip
except ImportError:
    try:
        from moviepy.editor import *
    except ImportError:
        print("❌ moviepy 라이브러리를 찾을 수 없습니다.")
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

def process_bumper_clip(path, target_size):
    """인트로/아웃트로 영상을 안전하게 로드하고 리사이즈하는 함수"""
    try:
        clip = VideoFileClip(path)
        # 배경 블랙 생성
        bg = ColorClip(size=target_size, color=(0,0,0), duration=clip.duration)
        
        # 가로 폭에 맞춰 리사이즈 (Aspect Ratio 유지)
        clip_resized = clip.resized(width=target_size[0])
        
        # 만약 리사이즈된 높이가 타겟보다 크면? -> 높이에 맞춤 (Fit)
        if clip_resized.h > target_size[1]:
            clip_resized = clip.resized(height=target_size[1])
            
        # 중앙 배치 합성
        return CompositeVideoClip([bg, clip_resized.with_position("center")])
    except Exception as e:
        print(f"⚠️ Bumper Clip 로드 실패 ({path}): {e}")
        return None

def create_video():
    mode = "video"
    if len(sys.argv) > 1: mode = sys.argv[1]

    is_shorts = "shorts" in mode
    is_news = "news" in mode
    
    story_path = "story.json"
    image_dir = "images"
    audio_dir = "audio"
    
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
    
    main_clips = []
    final_size = (720, 1280) if is_shorts else (1280, 720)

    # 1. 메인 컨텐츠 생성
    for i, scene in enumerate(scenes):
        idx = i + 1
        img_path = os.path.join(image_dir, f"image_{idx}.png")
        aud_path = os.path.join(audio_dir, f"audio_{idx}.mp3")
        
        if not os.path.exists(img_path) or not os.path.exists(aud_path):
            print(f"⚠️ 리소스 누락 (Scene {idx}), 건너뜀.")
            continue
            
        print(f"🎬 Scene {idx} 합성 중...")
        
        audio_clip = AudioFileClip(aud_path)
        duration = audio_clip.duration
        raw_img_clip = ImageClip(img_path).with_duration(duration)
        
        layers = []

        if is_shorts:
            # Shorts 레이아웃 (4:3 이미지 + 블랙박스)
            black_bg = ColorClip(size=final_size, color=(0, 0, 0)).with_duration(duration)
            layers.append(black_bg)
            
            resized_img = raw_img_clip.resized(width=720)
            centered_img = resized_img.with_position("center")
            layers.append(centered_img)
        else:
            # Video 레이아웃 (꽉 찬 화면)
            resized_img = raw_img_clip.resized(width=1280)
            layers.append(resized_img)

        # 출처 표시
        img_filename = f"image_{idx}.png"
        if img_filename in image_sources:
            source_text = f"Source: {image_sources[img_filename]}"
            source_clip = create_source_label(source_text, FONT_EN)
            source_y = 50 if is_shorts else 20
            source_clip = source_clip.with_position(("right", source_y)).with_duration(duration)
            layers.append(source_clip)

        # 자막 표시 (Shorts만)
        if is_shorts:
            narration = scene.get("narration", "")
            if narration:
                txt_clip = create_highlighted_text_clip(
                    narration, fontsize=45, color='white', highlight_color='yellow', 
                    max_width=650
                )
                txt_clip = txt_clip.with_position(("center", 950)).with_duration(duration)
                layers.append(txt_clip)

        composite = CompositeVideoClip(layers, size=final_size).with_audio(audio_clip)
        main_clips.append(composite)

    if not main_clips:
        print("❌ 생성된 클립이 없습니다.")
        return

    print("🎞️ 메인 컨텐츠 병합 중...")
    main_body_clip = concatenate_videoclips(main_clips, method="compose")
    
    # [Shorts 전용] 타이틀 오버레이 (영상 전체에 적용)
    if is_shorts and is_news:
        print("📝 타이틀 오버레이 추가...")
        title_clip = create_highlighted_text_clip(
            title_text, fontsize=50, color='white', highlight_color='#00ff00',
            is_title=True, max_width=680
        )
        title_clip = title_clip.with_position(("center", 100)).with_duration(main_body_clip.duration)
        main_body_clip = CompositeVideoClip([main_body_clip, title_clip], size=final_size)

    # ----------------------------------------------------
    # [Intro / Outro 결합 로직]
    # ----------------------------------------------------
    final_sequence = []
    
    # Intro 추가 (뉴스 쇼츠일 때만)
    if is_shorts and is_news and os.path.exists("assets/intro.mp4"):
        print("🎬 Intro 영상 추가 중...")
        intro_clip = process_bumper_clip("assets/intro.mp4", final_size)
        if intro_clip:
            final_sequence.append(intro_clip)
    
    # 메인 컨텐츠 추가
    final_sequence.append(main_body_clip)
    
    # Outro 추가 (뉴스 쇼츠일 때만)
    if is_shorts and is_news and os.path.exists("assets/outro.mp4"):
        print("🎬 Outro 영상 추가 중...")
        outro_clip = process_bumper_clip("assets/outro.mp4", final_size)
        if outro_clip:
            final_sequence.append(outro_clip)

    print("🚀 최종 영상 시퀀스 연결 중...")
    final_output_clip = concatenate_videoclips(final_sequence, method="compose")

    # 저장
    output_dir = "results"
    os.makedirs(output_dir, exist_ok=True)
    
    time_tag = datetime.now().strftime("%m%d_%H%M")
    base_name = "final_shorts" if is_shorts else "final_video"
    
    filename_timestamp = f"{base_name}_{time_tag}.mp4"
    filename_latest = f"{base_name}.mp4"
    
    output_path = os.path.join(output_dir, filename_timestamp)
    latest_path = os.path.join(output_dir, filename_latest)
    
    print(f"💾 렌더링 시작: {output_path}")
    
    final_output_clip.write_videofile(
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