import os
import json
import sys
import re
import numpy as np
from PIL import Image, ImageFont, ImageDraw
import shutil
from datetime import datetime

# Pillow 호환성 패치
if not hasattr(Image, 'ANTIALIAS'): Image.ANTIALIAS = Image.LANCZOS

try:
    from moviepy.editor import *
except ImportError:
    print("❌ moviepy 설치 필요: pip install moviepy"); sys.exit(1)

# 폰트 경로 설정 (한국어 폰트 필수)
FONT_EN = "C:/Windows/Fonts/arialbd.ttf"
FONT_KO = "C:/Windows/Fonts/malgunbd.ttf" # 맑은 고딕 볼드
FONT_DEFAULT = "arial.ttf"

def get_font_path(text):
    # 텍스트에 한글이 포함되어 있으면 무조건 한글 폰트 사용
    if re.search("[가-힣]", text):
        if os.path.exists(FONT_KO): return FONT_KO
        if os.path.exists("C:/Windows/Fonts/malgun.ttf"): return "C:/Windows/Fonts/malgun.ttf"
        if os.path.exists("C:/Windows/Fonts/gulim.ttc"): return "C:/Windows/Fonts/gulim.ttc"
    if os.path.exists(FONT_EN): return FONT_EN
    return FONT_DEFAULT

def create_highlighted_text_clip(text, fontsize, color='white', highlight_color='yellow', 
                               stroke_color='black', stroke_width=2, max_width=680, align='center', is_title=False):
    tokens = []
    
    # [핵심 수정] 이 부분이 한글을 지워버리는 원인이었습니다. 삭제했습니다!
    # try:
    #     if sys.platform == 'win32': text = text.encode('gbk', 'ignore').decode('gbk')
    # except: pass

    parts = text.split('*')
    for i, part in enumerate(parts):
        c = highlight_color if i % 2 == 1 else color
        words = part.split()
        for word in words: tokens.append({'text': word, 'color': c})

    font_path = get_font_path(text)
    try: font = ImageFont.truetype(font_path, fontsize)
    except: font = ImageFont.load_default()

    dummy_draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    space_w = dummy_draw.textbbox((0, 0), " ", font=font)[2]
    
    lines = []; current_line = []; current_w = 0
    for token in tokens:
        bbox = dummy_draw.textbbox((0, 0), token['text'], font=font)
        word_w = bbox[2] - bbox[0]
        if current_line and (current_w + word_w > max_width):
            lines.append(current_line); current_line = [token]; current_w = word_w + space_w
        else:
            current_line.append(token); current_w += word_w + space_w
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
    w = bbox[2] - bbox[0] + 20; h = bbox[3] - bbox[1] + 10
    img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    x, y = 10, 0
    for dx in range(-2, 3):
        for dy in range(-2, 3): draw.text((x+dx, y+dy), text, font=font, fill='black')
    draw.text((x, y), text, font=font, fill='white')
    return ImageClip(np.array(img))

def create_video():
    mode = "video"
    if len(sys.argv) > 1: mode = sys.argv[1]
    
    is_shorts = "shorts" in mode
    is_news = "news" in mode 
    
    story_path = "story.json"
    image_dir = "images"; audio_dir = "audio"
    intro_path = "assets/intro.mp4"; outro_path = "assets/outro.mp4"
    
    if not os.path.exists(story_path): print("❌ 오류: story.json 없음"); return

    try:
        with open(story_path, "r", encoding="utf-8") as f: data = json.load(f)
    except: print("❌ JSON 로드 실패"); return
    
    scenes = []
    title_text = "News Briefing"
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and "scenes" in data[0]:
        scenes = data[0]["scenes"]
        title_text = data[0].get("title", "News Briefing")
    elif isinstance(data, dict) and "scenes" in data:
        scenes = data["scenes"]
        title_text = data.get("title", "News Briefing")
    elif isinstance(data, list):
        scenes = data
        if len(scenes) > 0: title_text = scenes[0].get("title", "News Briefing")

    print(f"✅ 편집할 Scene 개수: {len(scenes)}")
    
    image_sources = {}
    sources_path = os.path.join(image_dir, "sources.json")
    if os.path.exists(sources_path):
        try:
            with open(sources_path, "r", encoding="utf-8") as f: image_sources = json.load(f)
        except: pass

    print(f"=== 편집(Editor) 시작 (Mode: {mode}) ===")
    
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

        # Intro/Outro 로직 (Play + Freeze)
        if is_intro_scene and os.path.exists(intro_path):
            try:
                print(f"   👉 Intro 적용 시도...")
                base_vid = VideoFileClip(intro_path).without_audio()
                if is_shorts: base_vid = base_vid.resize(width=720)
                else: base_vid = base_vid.resize(width=1280)

                if duration > base_vid.duration:
                    freeze_duration = duration - base_vid.duration
                    last_frame = base_vid.to_ImageClip(t=base_vid.duration - 0.01).set_duration(freeze_duration)
                    visual_clip = concatenate_videoclips([base_vid, last_frame])
                else:
                    visual_clip = base_vid.subclip(0, duration)
                is_video_asset = True
            except: is_video_asset = False

        elif is_outro_scene and os.path.exists(outro_path):
            try:
                print(f"   👉 Outro 적용 시도...")
                base_vid = VideoFileClip(outro_path).without_audio()
                if is_shorts: base_vid = base_vid.resize(width=720)
                else: base_vid = base_vid.resize(width=1280)

                if duration > base_vid.duration:
                    freeze_duration = duration - base_vid.duration
                    last_frame = base_vid.to_ImageClip(t=base_vid.duration - 0.01).set_duration(freeze_duration)
                    visual_clip = concatenate_videoclips([base_vid, last_frame])
                else:
                    visual_clip = base_vid.subclip(0, duration)
                is_video_asset = True
            except: is_video_asset = False
        
        if not is_video_asset:
            if os.path.exists(img_path):
                visual_clip = ImageClip(img_path).set_duration(duration)
                if is_shorts: visual_clip = visual_clip.resize(width=720)
                else: visual_clip = visual_clip.resize(width=1280)
            else:
                visual_clip = ColorClip(size=final_size, color=(0,0,0)).set_duration(duration)

        layers = []
        
        if is_shorts:
            layers.append(ColorClip(size=final_size, color=(0, 0, 0)).set_duration(duration))
            layers.append(visual_clip.set_position("center"))
        else:
            layers.append(visual_clip)

        if not is_video_asset:
            img_filename = f"image_{idx}.png"
            if img_filename in image_sources:
                source_clip = create_source_label(f"Source: {image_sources[img_filename]}", FONT_EN)
                source_clip = source_clip.set_position(("right", 50 if is_shorts else 20)).set_duration(duration)
                layers.append(source_clip)

        if is_shorts:
            narration = scene.get("narration", "")
            if narration:
                txt_clip = create_highlighted_text_clip(narration, fontsize=45, max_width=650)
                layers.append(txt_clip.set_position(("center", 950)).set_duration(duration))

        scene_composite = CompositeVideoClip(layers, size=final_size).set_audio(audio_clip)

        if is_intro_scene and is_video_asset: intro_clip_final = scene_composite
        elif is_outro_scene and is_video_asset: outro_clip_final = scene_composite
        else: body_clips.append(scene_composite)

    if not body_clips: print("❌ 본문 클립 생성 실패"); return

    print("🎞️ 클립 병합 및 타이틀 적용 중...")
    body_concat = concatenate_videoclips(body_clips, method="compose")
    
    if is_shorts and is_news:
        title_clip = create_highlighted_text_clip(title_text, fontsize=50, highlight_color='#00ff00', is_title=True)
        title_clip = title_clip.set_position(("center", 100)).set_duration(body_concat.duration)
        body_concat = CompositeVideoClip([body_concat, title_clip], size=final_size)
    
    final_sequence = []
    if intro_clip_final: final_sequence.append(intro_clip_final)
    final_sequence.append(body_concat)
    if outro_clip_final: final_sequence.append(outro_clip_final)

    final_clip = concatenate_videoclips(final_sequence, method="compose")
    output_dir = "results"; os.makedirs(output_dir, exist_ok=True)
    time_tag = datetime.now().strftime("%m%d_%H%M")
    base_name = "final_shorts" if is_shorts else "final_video"
    output_path = os.path.join(output_dir, f"{base_name}_{time_tag}.mp4")
    
    print(f"🚀 렌더링 시작: {output_path}")
    final_clip.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", threads=4, logger="bar")
    shutil.copy2(output_path, os.path.join(output_dir, f"{base_name}.mp4"))
    print(f"✨ 편집 완료! (저장: {output_path})")

if __name__ == "__main__":
    create_video()