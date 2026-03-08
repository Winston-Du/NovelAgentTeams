#!/usr/bin/env python3
"""Extract chapters 2-10 from the continuous writing log file.

Key insights from log analysis:
- The chapter_id in the YAML output does NOT match the actual chapter number
  (the AI agent keeps reusing old IDs). The 📖 section markers define the real chapter.
- Each section (📖 to next 📖) contains one or more crew iterations
- Within each section, we want the LAST 资深校对 (proofreader) final answer's
  final_content that contains real text (not placeholder)
- Content is wrapped in box-drawing chars: │  content  │
- We must skip placeholder '[优化后的完整章节]' blocks
- The chapter_title in the YAML also doesn't match the 📖 description,
  so we use the 📖 marker description as the authoritative title
"""

import re
import os

LOG_FILE = "logs/continuous_writing_20260306_083714.log"
OUTPUT_DIR = "output/chapters"


def read_log():
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return f.readlines()


def clean_line(raw_line):
    """Remove box-drawing │ chars and consistent indentation from a log line."""
    line = raw_line.rstrip("\n").rstrip()

    # Remove trailing │ and spaces
    line = re.sub(r"\s*│\s*$", "", line)

    # Remove leading │ and up to 2 spaces after it
    line = re.sub(r"^│\s{0,2}", "", line)

    # Remove YAML block scalar indentation (6 spaces for final_content content)
    line = re.sub(r"^\s{4,6}", "", line)

    return line


def extract_content_from_proofreader(lines, answer_start):
    """Extract final_content from a 资深校对 Final Answer block.

    answer_start points to the '✅ Agent Final Answer' line.
    Returns content string or None if placeholder/empty.
    """
    # Search for final_content: | within ~300 lines
    for j in range(answer_start, min(answer_start + 300, len(lines))):
        raw = lines[j]
        inner = re.sub(r"\s*│\s*$", "", re.sub(r"^│\s{0,2}", "", raw.rstrip()))

        if re.match(r"\s*final_content:\s*\|", inner.strip()):
            # Found the start, now extract content lines
            content_lines = []
            found_real = False
            k = j + 1

            while k < len(lines):
                raw_k = lines[k]
                raw_stripped = raw_k.strip()

                # End conditions
                if raw_stripped.startswith("╰─"):
                    break

                inner_k = re.sub(
                    r"\s*│\s*$", "", re.sub(r"^│\s{0,2}", "", raw_k.rstrip())
                )
                inner_k_stripped = inner_k.strip()

                # End markers (YAML keys at same or lower indent)
                if re.match(
                    r"\s{0,4}(proofreading_log|word_count|character_updates|updated_character_cards|plot_threads|needs_revision|revision_note|quality_score|self_check_report):",
                    inner_k_stripped,
                ):
                    break

                if inner_k_stripped == "```":
                    break

                # Placeholder - skip this entire block
                if "[优化后的完整章节]" in inner_k_stripped:
                    return None

                cleaned = clean_line(raw_k)
                if cleaned.strip():
                    found_real = True
                content_lines.append(cleaned)
                k += 1

            if not found_real:
                return None

            # Trim blank lines
            while content_lines and not content_lines[-1].strip():
                content_lines.pop()
            while content_lines and not content_lines[0].strip():
                content_lines.pop(0)

            return "\n".join(content_lines)

    return None


def extract_chapters():
    lines = read_log()
    total_lines = len(lines)

    # Step 1: Find 📖 chapter markers
    chapter_markers = []
    for i, line in enumerate(lines):
        m = re.search(r"📖 第 (\d+) 章[：:]\s*(.*)", line)
        if m:
            ch_num = int(m.group(1))
            ch_desc = m.group(2).strip()
            chapter_markers.append((i, ch_num, ch_desc))

    # Step 2: Find 📊 completion markers
    completion_markers = {}
    for i, line in enumerate(lines):
        m = re.search(r"📊 第 (\d+) 章完成", line)
        if m:
            completion_markers[int(m.group(1))] = i

    print(
        f"Found {len(chapter_markers)} chapter markers, {len(completion_markers)} completion markers"
    )

    # Step 3: For each chapter, find the last 资深校对 answer within the section
    chapters = {}

    for ci, (start_line, ch_num, ch_desc) in enumerate(chapter_markers):
        end_line = completion_markers.get(
            ch_num,
            chapter_markers[ci + 1][0]
            if ci + 1 < len(chapter_markers)
            else total_lines,
        )

        # Find all 资深校对 Final Answers in range [start_line, end_line]
        proofreader_answers = []
        for j in range(start_line, end_line + 1):
            if j < total_lines and "✅ Agent Final Answer" in lines[j]:
                for k in range(j, min(j + 5, total_lines)):
                    if "资深校对" in lines[k]:
                        proofreader_answers.append(j)
                        break

        print(f"\n📖 第 {ch_num} 章: {ch_desc}")
        print(
            f"  Section: lines {start_line + 1}-{end_line + 1}, {len(proofreader_answers)} proofreader answers"
        )

        # Try from last to first
        content = None
        for pa in reversed(proofreader_answers):
            content = extract_content_from_proofreader(lines, pa)
            if content is not None:
                print(f"  ✅ Using answer at line {pa + 1}: {len(content)} chars")
                break
            else:
                print(f"  ⏭️  Skipping placeholder at line {pa + 1}")

        if content:
            chapters[ch_num] = (ch_desc, content)
        else:
            print(f"  ❌ No real content found!")

    return chapters


def save_chapters(chapters):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for ch_num in range(2, 11):
        if ch_num not in chapters:
            print(f"WARNING: Chapter {ch_num} not found!")
            continue

        title, content = chapters[ch_num]
        filename = f"chapter_{ch_num}_final.md"
        filepath = os.path.join(OUTPUT_DIR, filename)

        md_content = f"# 第 {ch_num} 章\n\n**{title}**\n\n{content}\n"

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)

        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", content))
        print(f"  Saved {filepath} (~{chinese_chars} 字)")


if __name__ == "__main__":
    chapters = extract_chapters()
    print(f"\n{'=' * 60}")
    print(f"Extracted {len(chapters)} chapters: {sorted(chapters.keys())}")
    print(f"{'=' * 60}\n")
    save_chapters(chapters)
