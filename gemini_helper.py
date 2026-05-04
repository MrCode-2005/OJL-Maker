import json
import re
import time
import urllib.request
from datetime import datetime

# You can change this to any OpenRouter model.
# Example: "google/gemini-2.5-flash", "anthropic/claude-3-haiku", "meta-llama/llama-3-8b-instruct"
OPENROUTER_MODEL = "google/gemini-2.5-flash"


# ─────────────────────────────────────────────
# ✅ PARSE STRUCTURED ENTRY (skip AI)
# ─────────────────────────────────────────────
def parse_structured_entry(work_text: str) -> dict:
    """
    Parse user-provided structured text into journal entry fields.
    Returns a dict with my_space, tasks_carried_out, key_learnings, tools_used, special_achievements.
    Returns None if the text is not in a recognized structured format.

    Recognized format (** markers are optional):
        **MY SPACE:** content
        **Tasks Carried Out Today:** content
        **Key Learnings/Observations:** content
        **Tools, Equipment, Technology or Techniques Used:** content
        **Special Achievements:** content
    """
    if not work_text or not work_text.strip():
        return None

    # Define field header patterns in order they typically appear
    # Supports formats like:
    # **MY SPACE:**
    # ### MY SPACE
    field_headers = [
        ("my_space",             r"(?:^|\n)\s*(?:#{1,6}\s+|\*{0,2}\s*)MY\s*SPACE[^\n:]*\*{0,2}\s*:?"),
        ("tasks_carried_out",    r"(?:^|\n)\s*(?:#{1,6}\s+|\*{0,2}\s*)Tasks?\s*Carried\s*Out[^\n:]*\*{0,2}\s*:?"),
        ("key_learnings",        r"(?:^|\n)\s*(?:#{1,6}\s+|\*{0,2}\s*)Key\s*Learnings?[^\n:]*\*{0,2}\s*:?"),
        ("tools_used",           r"(?:^|\n)\s*(?:#{1,6}\s+|\*{0,2}\s*)Tools?[\s,/]*(?:Equipment|Technology|Technologies|Techniques|Used)[^\n:]*\*{0,2}\s*:?"),
        ("special_achievements", r"(?:^|\n)\s*(?:#{1,6}\s+|\*{0,2}\s*)Special\s*Achievements?[^\n:]*\*{0,2}\s*:?"),
    ]

    # Find all field positions
    positions = []
    for field_name, pattern in field_headers:
        match = re.search(pattern, work_text, re.IGNORECASE)
        if match:
            positions.append((match.start(), match.end(), field_name))

    # Need at least 2 recognized fields to consider it "structured"
    if len(positions) < 2:
        return None

    # Sort by position in text
    positions.sort(key=lambda x: x[0])

    # Extract content between each header
    fields = {}
    for i, (start, end, field_name) in enumerate(positions):
        if i + 1 < len(positions):
            content = work_text[end:positions[i + 1][0]]
        else:
            content = work_text[end:]

        # Clean up the content
        content = content.strip()
        # Remove leading/trailing ** markdown
        content = re.sub(r'^\*{2,}\s*', '', content)
        content = re.sub(r'\s*\*{2,}$', '', content)
        # Remove stray Day headers
        content = re.sub(r'^#{1,}\s*Day\s*\d+\s*$', '', content, flags=re.MULTILINE | re.IGNORECASE)
        # Remove document titles (e.g. "# 📘 OJL Logbook (Corrected...)")
        content = re.sub(r'^#\s+.*$', '', content, flags=re.MULTILINE)
        # Remove horizontal rules (---)
        content = re.sub(r'^-{3,}\s*$', '', content, flags=re.MULTILINE)
        content = content.strip()

        fields[field_name] = content

    return fields


# ─────────────────────────────────────────────
# ✅ PARSE MULTI-DAY STRUCTURED TEXT (skip AI splitting)
# ─────────────────────────────────────────────
def parse_multi_day_text(work_description: str, dates: list, num_days: int) -> list:
    """
    Parse a multi-day structured work description into per-day entries.
    Splits on '## Day N' or 'Day N' headers.
    Returns list of {day, date, work} dicts, or None if not in multi-day format.

    Expected input format:
        ## Day 1
        **MY SPACE:** ...
        **Tasks Carried Out Today:** ...
        ...

        ## Day 2
        **MY SPACE:** ...
        ...
    """
    if not work_description or not work_description.strip():
        return None

    # Split by day headers: ## Day 1, ## Day 2, Day 1, Day 2, etc.
    day_pattern = r'(?:^|\n)\s*(?:#{1,3}\s*)?Day\s+(\d+)\s*\n'
    splits = re.split(day_pattern, work_description, flags=re.IGNORECASE)

    # splits will be: [text_before_day1, "1", day1_content, "2", day2_content, ...]
    # If no splits found, the format is not multi-day
    if len(splits) < 3:
        return None

    day_entries = []
    # Start from index 1 (skip text before first Day header)
    i = 1
    while i < len(splits) - 1:
        day_num = int(splits[i])
        day_content = splits[i + 1].strip()
        day_entries.append((day_num, day_content))
        i += 2

    if not day_entries:
        return None

    # Verify at least one entry has structured fields
    has_structured = any(parse_structured_entry(content) for _, content in day_entries)
    if not has_structured:
        return None

    # Build result list matching the expected format
    result = []
    for idx, (day_num, content) in enumerate(day_entries[:num_days]):
        formatted_date = format_date(dates[idx]) if idx < len(dates) else ""
        result.append({
            "day": idx + 1,
            "date": formatted_date,
            "work": content  # Preserve the full structured text
        })

    return result


# ─────────────────────────────────────────────
# ✅ DATE FORMATTER
# ─────────────────────────────────────────────
def format_date(date_str: str) -> str:
    def _ordinal(day: int) -> str:
        if 11 <= day <= 13:
            return f"{day}th"
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        return f"{day}{suffix}"

    try:
        for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%y"]:
            try:
                parsed = datetime.strptime(date_str, fmt)
                # Format as "2nd February 2026"
                return f"{_ordinal(parsed.day)} {parsed.strftime('%B')} {parsed.year}"
            except ValueError:
                continue
        return date_str
    except Exception:
        return date_str


# Removed legacy AI processing endpoints. System is now fully offline via Regex parsers above.