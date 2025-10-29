import re


def fix_broken_sentences(text):
    """
    Fixes broken sentences by merging sentence fragments with the previous speaker.
    If a speaker only has a broken sentence fragment, the entire speaker entry is removed
    and the fragment is merged with the previous speaker.
    """
    # Pattern to match speaker tags
    speaker_pattern = r'\[Person\d+\]:'

    # Find all speakers and their positions
    matches = list(re.finditer(speaker_pattern, text))

    if not matches:
        return text

    # Extract segments with speaker and content
    segments = []
    for i, match in enumerate(matches):
        speaker = match.group()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        segments.append({'speaker': speaker, 'content': content})

    # Process segments to merge broken sentences
    result = []

    for i, segment in enumerate(segments):
        content = segment['content']
        speaker = segment['speaker']

        # Check if content starts with a lowercase letter (broken sentence)
        if content and content[0].islower() and result:
            # Check if entire content is just a broken fragment
            # (starts with lowercase and ends with period, no capital letter after first word)
            match = re.search(r'\.\s+[A-Z]', content)

            if not match:
                # Entire content is just a fragment, merge all with previous speaker
                # and don't add this speaker at all
                result[-1]['content'] += ' ' + content
            else:
                # There's more content after the broken sentence
                split_pos = match.start() + 1  # Include the period
                broken_part = content[:split_pos].strip()
                remaining = content[split_pos:].strip()

                # Merge broken part with previous speaker
                result[-1]['content'] += ' ' + broken_part

                # Add current speaker with remaining content
                result.append({'speaker': speaker, 'content': remaining})
        else:
            # Normal segment, add as is
            result.append({'speaker': speaker, 'content': content})

    # Reconstruct the text
    output = []
    for seg in result:
        output.append(f"{seg['speaker']} {seg['content']}")

    return '\n\n'.join(output)



# Process and print the result
for i in range(1,2):
    input_file = f'subtitles/{i}.vtt'
    output_file = f'subtitles/{i}_corrected.vtt'

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            text = f.read()

        # Process the text
        corrected_text = fix_broken_sentences(text)

        # Write to output file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(corrected_text)

        print(f"✓ Processing complete!")
        print(f"  Input:  {input_file}")
        print(f"  Output: {output_file}")
    except FileNotFoundError:
        print(f"Error: File '{input_file}' not found.")
    except Exception as e:
        print(f"Error: {e}")

