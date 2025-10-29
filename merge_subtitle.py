import re
import os
from datetime import timedelta
from difflib import SequenceMatcher
import numpy as np
from tqdm import tqdm


def parse_vtt_time(time_str):
    """Convert VTT timestamp to seconds"""
    time_str = time_str.strip()
    parts = time_str.split(':')
    if len(parts) == 3:  # HH:MM:SS.mmm
        h, m, s = parts
        if '.' in s:
            s, ms = s.split('.')
            return int(h) * 3600 + int(m) * 60 + int(s) + float(ms) / 1000
        else:
            return int(h) * 3600 + int(m) * 60 + int(s)
    elif len(parts) == 2:  # MM:SS.mmm
        m, s = parts
        if '.' in s:
            s, ms = s.split('.')
            return int(m) * 60 + int(s) + float(ms) / 1000
        else:
            return int(m) * 60 + int(s)


def parse_transcript_time(time_str):
    """Convert transcript timestamp [H:MM:SS] to seconds"""
    time_str = time_str.strip('[]').strip()
    parts = time_str.split(':')
    h, m, s = parts
    return int(h) * 3600 + int(m) * 60 + int(s)


def parse_vtt(vtt_content):
    """Parse VTT file and return list of segments"""
    segments = []
    lines = vtt_content.strip().split('\n')

    i = 0
    while i < len(lines):
        line = lines[i].strip()

        # Skip WEBVTT header and empty lines
        if line == 'WEBVTT' or line == '' or line.isdigit():
            i += 1
            continue

        # Check if this is a timestamp line
        if '-->' in line:
            times = line.split('-->')
            start = parse_vtt_time(times[0])
            end = parse_vtt_time(times[1])

            # Collect subtitle text (next lines until empty line)
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip() != '':
                # Remove HTML font tags
                text = re.sub(r'<font[^>]*>', '', lines[i])
                text = re.sub(r'</font>', '', text)
                text = text.strip()
                if text:
                    text_lines.append(text)
                i += 1

            if text_lines:
                segments.append({
                    'start': start,
                    'end': end,
                    'text': ' '.join(text_lines)
                })
        else:
            i += 1

    return segments


def parse_transcript(transcript_content):
    """Parse automatic transcript and return speaker segments"""
    speakers = []
    lines = transcript_content.strip().split('\n')

    for line in lines:
        # Match pattern: Person# [H:MM:SS - H:MM:SS]:
        match = re.match(r'(Person\d+)\s+\[(\d+:\d+:\d+)\s*-\s*(\d+:\d+:\d+)\]:', line)
        if match:
            speaker = match.group(1)
            start = parse_transcript_time(match.group(2))
            end = parse_transcript_time(match.group(3))

            speakers.append({
                'speaker': speaker,
                'start': start,
                'end': end
            })

    return speakers


def normalize_text(text):
    """标准化文本用于比较"""
    # 转小写，去除标点和多余空格
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = ' '.join(text.split())
    return text


def is_background_sound(text):
    """检测是否是背景音/音效"""
    # 包含*号，或者太短，或者全是符号
    if '*' in text or len(text.strip()) < 10:
        return True
    # 检测是否主要是符号
    if len(re.sub(r'[^\w\s]', '', text)) < 5:
        return True
    return False


def text_similarity_bidirectional(text1, text2):
    """
    双向相似度：自动识别哪个文本短，计算包含度
    """
    words1 = text1.split()
    words2 = text2.split()

    if not words1 or not words2:
        return 0.0

    # 选择较短的文本作为基准
    if len(words1) <= len(words2):
        short_words = words1
        long_words_set = set(words2)
    else:
        short_words = words2
        long_words_set = set(words1)

    # 计算短文本的词有多少在长文本中
    matches = sum(1 for word in short_words if word in long_words_set)

    return matches / len(short_words)


def detect_delay_first_match(vtt_segments, transcript_content):
    """
    使用视频开头前10秒的第一个匹配点检测延迟

    Args:
        vtt_segments: VTT片段列表
        transcript_content: 转录文本内容
    """
    TIME_WINDOW = 20  # 只用前10秒

    # 从transcript提取前10秒的文本
    pattern = r'(Person\d+)\s*\[(\d+:\d+:\d+)\s*-\s*(\d+:\d+:\d+)\]:\s*\n(.*?)(?=\nPerson\d+\s*\[|\Z)'
    matches = re.findall(pattern, transcript_content, flags=re.DOTALL)

    transcript_data = []
    for person, start_str, end_str, speech in matches:
        start = parse_transcript_time(start_str)

        # 只使用前10秒的内容
        if start > TIME_WINDOW:
            break

        # 将整段话作为一个单元
        speech_clean = " ".join(speech.strip().split())
        if len(speech_clean) > 20:
            transcript_data.append({
                'text': normalize_text(speech_clean),
                'start': start,
                'person': person
            })

    # 只检测前10秒的VTT片段，找到第一个匹配点
    for vtt_seg in vtt_segments:
        print(vtt_seg)
        # 只检测前10秒
        if vtt_seg['start'] > TIME_WINDOW:
            break

        if is_background_sound(vtt_seg['text']):
            continue

        vtt_norm = normalize_text(vtt_seg['text'])
        if len(vtt_norm) < 10:
            continue

        # 找最相似的transcript片段
        best_similarity = 0
        best_trans = None

        for trans in transcript_data:
            trans['text'] = trans['text'][:len(vtt_norm)]
            similarity = text_similarity_bidirectional(vtt_norm, trans['text'])
            if similarity > best_similarity:
                best_similarity = similarity
                best_trans = trans

        # 如果相似度够高，立即返回这个延迟
        if best_similarity > 0.4 and best_trans:
            delay = vtt_seg['start'] - best_trans['start']
            if 0 < delay < 15:
                delay = round(delay, 1)
                print(f"   ✓ 第一个匹配点: '{vtt_seg['text'][:40]}...'")
                print(f"   ✓ 相似度={best_similarity:.2f}, 延迟={delay}s")
                return delay

    # 如果没找到匹配点，使用默认值
    print(f"   ⚠ 未找到匹配点，使用默认延迟1秒")
    return 1.0


def find_speaker(vtt_segment, speakers, delay=0):
    """Find the speaker with the most time overlap

    Args:
        vtt_segment: VTT segment with 'start' and 'end' times
        speakers: List of speaker segments
        delay: Seconds to subtract from VTT times to compensate for caption delay
    """
    # 将VTT时间往前调整，补偿延迟
    vtt_start = vtt_segment['start'] - delay
    vtt_end = vtt_segment['end'] - delay

    best_speaker = 'Unknown'
    max_overlap = 0

    for speaker_seg in speakers:
        # Calculate overlap
        overlap_start = max(vtt_start, speaker_seg['start'])
        overlap_end = min(vtt_end, speaker_seg['end'])
        overlap = max(0, overlap_end - overlap_start)

        if overlap > max_overlap:
            max_overlap = overlap
            best_speaker = speaker_seg['speaker']

    return best_speaker


def seconds_to_vtt_time(seconds):
    """Convert seconds to VTT timestamp format"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def combine_files(vtt_path, transcript_path, vtt_old):
    """Combine VTT and transcript files with automatic delay detection"""
    # Read files
    with open(vtt_old, 'r', encoding='utf-8') as f:
        vtt_content = f.read()

    with open(transcript_path, 'r', encoding='utf-8') as f:
        transcript_content = f.read()

    # Parse both files
    vtt_segments = parse_vtt(vtt_content)
    speakers = parse_transcript(transcript_content)

    # Auto-detect delay (只用第一个匹配点)
    delay = detect_delay_first_match(vtt_segments, transcript_content)
    print(f"📊 检测到延迟: {delay}秒")

    # Match speakers to VTT segments
    current_speaker = None
    current_texts = []
    output_lines = []

    for segment in vtt_segments:
        # 跳过背景音
        if is_background_sound(segment['text']):
            continue

        speaker = find_speaker(segment, speakers, delay=delay)

        # If speaker changes, write previous speaker's text
        if speaker != current_speaker and current_speaker is not None:
            combined_text = ' '.join(current_texts)
            output_lines.append(f"[{current_speaker}]: {combined_text}")
            output_lines.append('')
            current_texts = []

        current_speaker = speaker
        current_texts.append(segment['text'])

    # Don't forget the last speaker
    if current_texts:
        combined_text = ' '.join(current_texts)
        output_lines.append(f"[{current_speaker}]: {combined_text}")

    # Write output
    with open(vtt_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

    print(f"✓ Combined file saved to: {vtt_path}")
    print(f"✓ Processed {len(vtt_segments)} subtitle segments\n")


def convert_transcript_to_lines(input_file, output_file):
    """
    Convert transcript with timestamps into a clean format:
    [PersonX]: content
    One line per speaker turn.
    """
    with open(input_file, "r", encoding="utf-8") as f:
        text = f.read()

    # Remove headers or separators like "===="
    text = re.sub(r"=+\s*Video Transcription Results\s*=+", "", text, flags=re.IGNORECASE)
    text = text.strip()

    # Pattern: Match blocks like "Person11 [0:00:00 - 0:00:14]:\nSpeech..."
    pattern = r"(Person\d+)\s*\[[^\]]+\]:\s*\n(.*?)(?=\nPerson\d+\s*\[|\Z)"

    matches = re.findall(pattern, text, flags=re.DOTALL)

    lines = []
    for person, speech in matches:
        # Normalize whitespace and remove line breaks
        speech = " ".join(speech.strip().split())
        lines.append(f"[{person}]: {speech}")

    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n\n".join(lines))

    print(f"✅ Converted transcript saved to: {output_file}")
    print(f"💬 Total lines written: {len(lines)}")


# Usage
if __name__ == "__main__":
    # Example usage
    for idx in tqdm(range(287,288)):
        vtt_file = f"subtitles/{idx}.vtt"
        vtt_old_file = f"subtitles/{idx}_old.vtt"
        transcript_file = f"transcripts/transcription_{idx}.txt"

        if os.path.exists(vtt_old_file):
            try:
                combine_files(vtt_file, transcript_file, vtt_old_file)
            except Exception as e:
                print(f"❌ Error processing {idx}: {e}")
        else:
            try:
                convert_transcript_to_lines(transcript_file, vtt_file)
            except Exception as e:
                print(f"❌ Error converting {idx}: {e}")