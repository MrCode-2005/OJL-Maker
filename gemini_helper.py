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
        ("my_space",             r"(?:^|\n)\s*(?:#{1,6}\s+|\*{0,2}\s*)MY\s*SPACE[^\n:]*:?\s*\*{0,2}\s*"),
        ("tasks_carried_out",    r"(?:^|\n)\s*(?:#{1,6}\s+|\*{0,2}\s*)Tasks?\s*Carried\s*Out[^\n:]*:?\s*\*{0,2}\s*"),
        ("key_learnings",        r"(?:^|\n)\s*(?:#{1,6}\s+|\*{0,2}\s*)Key\s*Learnings?[^\n:]*:?\s*\*{0,2}\s*"),
        ("tools_used",           r"(?:^|\n)\s*(?:#{1,6}\s+|\*{0,2}\s*)Tools?[\s,/]*(?:Equipment|Technology|Technologies|Techniques|Used)[^\n:]*:?\s*\*{0,2}\s*"),
        ("special_achievements", r"(?:^|\n)\s*(?:#{1,6}\s+|\*{0,2}\s*)Special\s*Achievements?[^\n:]*:?\s*\*{0,2}\s*"),
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


# ─────────────────────────────────────────────
# ✅ SAFE OPENROUTER CALL (handles 429)
# ─────────────────────────────────────────────
def call_openrouter(api_key, prompt, retries=3):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000", # Required by OpenRouter
        "X-Title": "OJT Journal Maker" # Required by OpenRouter
    }
    data = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.4,
        "top_p": 0.9,
        "max_tokens": 4000,
    }

    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req) as response:
                response_data = json.loads(response.read().decode('utf-8'))
                
                text = response_data['choices'][0]['message']['content'].strip()
                # Remove markdown code fences (```json ... ``` or ``` ... ```)
                text = re.sub(r'^```(?:json)?\s*\n?', '', text, flags=re.MULTILINE)
                text = re.sub(r'\n?\s*```\s*$', '', text, flags=re.MULTILINE)
                # Remove any text before the first [ or {
                json_start = None
                for idx, ch in enumerate(text):
                    if ch in '[{':
                        json_start = idx
                        break
                if json_start is not None:
                    text = text[json_start:]
                # Remove any text after the last ] or }
                json_end = None
                for idx in range(len(text) - 1, -1, -1):
                    if text[idx] in ']}':
                        json_end = idx
                        break
                if json_end is not None:
                    text = text[:json_end + 1]
                # Remove backtick characters inside strings (e.g. `npx create-next-app`)
                text = text.replace('`', '')
                return text

        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5) # Wait before retry
            else:
                error_body = e.read().decode()
                raise Exception(f"OpenRouter Error {e.code}: {error_body}")
        except Exception as e:
            if "429" in str(e):
                time.sleep(5)
            else:
                raise e
    raise Exception("OpenRouter API failed after retries")


# ─────────────────────────────────────────────
# ✅ SPLIT WORK INTO DAYS
# ─────────────────────────────────────────────
def split_work_into_days(api_key: str, work_description: str, dates: list, num_days: int) -> list:
    prompt = f"""
You are a professional OJT training supervisor.

Divide the following work into EXACTLY {num_days} day-wise entries.

RULES:
- No HR / meetings / company talk
- Only technical/project work
- Each day must be unique
- Maintain progression:
  understanding → planning → implementation → debugging → improvement
- Each day: 2–4 meaningful sentences
- No generic phrases
- No repetition
- No empty or incomplete entries
- Use college/student-level tools (avoid professional tools like Jira, Azure, enterprise software)

OUTPUT JSON ONLY:
[
  {{ "day": 1, "work": "..." }}
]

WORK:
{work_description}
"""

    text = call_openrouter(api_key, prompt)
    daily_splits = json.loads(text)

    result = []
    for i, item in enumerate(daily_splits[:num_days]):
        formatted_date = format_date(dates[i]) if i < len(dates) else ""
        result.append({
            "day": i + 1,
            "date": formatted_date,
            "work": item["work"]
        })

    return result


# ─────────────────────────────────────────────
# ✅ GENERATE ALL JOURNAL ENTRIES IN ONE CALL 🚀
# ─────────────────────────────────────────────
def generate_all_journals(api_key: str, daily_data: list) -> list:
    combined_input = "\n".join([
        f"Day {d['day']} ({d['date']}): {d['work']}"
        for d in daily_data
    ])

    prompt = f"""
Generate professional OJT daily journal entries for college students.

RULES:
- Each day must be unique
- No repetition
- No HR/company content
- Keep concise and realistic
- Avoid professional/enterprise tools (no Jira, Azure, Salesforce, etc.)
- Use college-friendly tools: Python, JavaScript, Git, SQL, VS Code, Linux, React, etc.

For EACH day return:
- my_space: Minimum 4 lines of detailed personal reflection
- tasks_carried_out: List items separated by NEWLINE (NOT array)
- key_learnings: List items separated by NEWLINE (NOT array)
- tools_used: comma-separated list
- special_achievements: 1-2 lines (NEVER "N/A")

OUTPUT JSON (use plain text with newlines for multi-line fields):
[
  {{
    "day": 1,
    "my_space": "reflection text",
    "tasks_carried_out": "Task 1\\nTask 2\\nTask 3",
    "key_learnings": "Learning 1\\nLearning 2",
    "tools_used": "tool1, tool2, tool3",
    "special_achievements": "achievement text"
  }}
]

INPUT:
{combined_input}
"""

    text = call_openrouter(api_key, prompt)
    return json.loads(text)


# ─────────────────────────────────────────────
# ✅ SINGLE JOURNAL ENTRY (for backward compatibility)
# ─────────────────────────────────────────────
def generate_journal_entry(api_key: str, date: str, work: str) -> dict:
    formatted_date = format_date(date)

    prompt = f"""Generate a professional internship daily journal entry for a college student.

Date: {formatted_date}
Work Done: {work}

Return ONLY a valid JSON object (no markdown, no explanation):
{{
  "my_space": "Detailed personal reflection (Minimum 4 sentences/lines)",
  "tasks_carried_out": "Task 1\\nTask 2\\nTask 3\\nTask 4",
  "key_learnings": "Learning 1\\nLearning 2\\nLearning 3",
  "tools_used": "tool1, tool2, tool3",
  "special_achievements": "Achievement description (1-2 sentences)"
}}

IMPORTANT:
- Use college/student-level tools only (Python, JavaScript, Git, VS Code, Linux, React, etc.)
- AVOID professional tools like Jira, Azure, Salesforce, enterprise software
- Use plain newlines (\\n) between items for multi-line fields, NOT JSON arrays
- Each task/learning should be a complete sentence
- Keep it concise, professional, realistic, and non-repetitive"""

    text = call_openrouter(api_key, prompt)
    return json.loads(text)