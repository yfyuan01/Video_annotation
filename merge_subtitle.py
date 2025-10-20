import re
from datetime import timedelta


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


def find_speaker(vtt_segment, speakers):
    """Find the speaker with the most time overlap"""
    vtt_start = vtt_segment['start']
    vtt_end = vtt_segment['end']

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
    """Combine VTT and transcript files"""
    # Read files
    with open(vtt_path, 'r', encoding='utf-8') as f:
        vtt_content = f.read()

    with open(transcript_path, 'r', encoding='utf-8') as f:
        transcript_content = f.read()

    # Parse both files
    vtt_segments = parse_vtt(vtt_content)
    speakers = parse_transcript(transcript_content)

    # Match speakers to VTT segments
    current_speaker = None
    current_texts = []
    output_lines = []

    for segment in vtt_segments:
        speaker = find_speaker(segment, speakers)

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
    os.rename(vtt_path, vtt_old)
    with open(vtt_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))

    print(f"✓ Combined file saved to: {vtt_path}")
    print(f"✓ Processed {len(vtt_segments)} subtitle segments")
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
import os
# Usage
from tqdm import tqdm
if __name__ == "__main__":
    # Example usage
    idx = 1
    for idx in tqdm(range(5,421)):
        vtt_file = f"subtitles/{idx}.vtt"
        vtt_old_file = f"subtitles/{idx}_old.vtt"
        transcript_file = f"transcripts/transcription_{idx}.txt"
        # output_file = "combined_output.vtt"
        if os.path.exists(vtt_file):
            combine_files(vtt_file, transcript_file, vtt_old_file)
        else:
            convert_transcript_to_lines(transcript_file, vtt_file)
