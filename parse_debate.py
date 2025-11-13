#!/usr/bin/env python3
"""Parse Discord conversation export into debate format"""

import re

# Read the raw Discord export
with open(r'd:\womp debate.txt', 'r', encoding='utf-8') as f:
    lines = f.readlines()

messages = []
current_speaker = None
current_message = []

for line in lines:
    line = line.rstrip('\n')

    # Check if this line starts with a username and timestamp
    # Pattern: "username — HH:MM AM/PM"
    match = re.match(r'^(.+?)\s*—\s*\d+:\d+\s*(?:AM|PM)\s*$', line)

    if match:
        # Save previous message if exists
        if current_speaker and current_message:
            message_text = ' '.join(current_message)
            # Clean up speaker name (remove spaces, special chars)
            speaker_clean = current_speaker.replace(' ', '_').replace('✨', '').replace('💣', '')
            messages.append(f"{speaker_clean}: {message_text}")

        # Start new speaker
        current_speaker = match.group(1).strip()
        current_message = []
    elif line.strip():
        # Continuation of current speaker's message
        # Skip lines that are just "Image" or empty
        if line.strip() not in ['Image', 'Spoiler: I just did this']:
            current_message.append(line.strip())

# Don't forget the last message
if current_speaker and current_message:
    message_text = ' '.join(current_message)
    speaker_clean = current_speaker.replace(' ', '_').replace('✨', '').replace('💣', '')
    messages.append(f"{speaker_clean}: {message_text}")

# Write formatted output
with open(r'd:\womp debate.txt', 'w', encoding='utf-8') as f:
    for msg in messages:
        f.write(msg + '\n\n')

print(f"Formatted {len(messages)} messages from the debate")
