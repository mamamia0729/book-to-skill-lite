#!/usr/bin/env python3
"""book-to-skill-lite: Turn technical books (PDF) into Claude Desktop skills.

Zero-token extraction. Builds layer-based skill zips with diagram placeholders
and teaching rules baked in. Designed for budget-conscious usage.

Usage:
    python book_to_skill_lite.py config.json
"""

import json
import os
import re
import sys
import zipfile
from pathlib import Path

try:
    import pymupdf
except ImportError:
    import fitz as pymupdf


def extract_text_from_pdf(pdf_path, start_page=None, end_page=None):
    """Extract text from PDF pages. Returns list of (page_num, text) tuples."""
    doc = pymupdf.open(pdf_path)
    pages = []
    start = (start_page - 1) if start_page else 0
    end = end_page if end_page else len(doc)
    for i in range(start, min(end, len(doc))):
        text = doc[i].get_text()
        if text.strip():
            pages.append((i + 1, text))
    doc.close()
    return pages


def get_toc(pdf_path):
    """Extract table of contents from PDF."""
    doc = pymupdf.open(pdf_path)
    toc = doc.get_toc()
    doc.close()
    return toc


def insert_diagram_placeholders(text):
    """Replace figure references with diagram placeholders.

    Scans for 'Figure X-Y' patterns and surrounding context to build
    descriptive placeholders that Claude can reconstruct as diagrams.
    Only emits one placeholder per figure number (first occurrence with
    the best description wins).
    """
    lines = text.split('\n')
    result = []
    seen_figures = {}

    # Pattern for figure references like "Figure 1-2" or "Figure 12-3"
    figure_pattern = re.compile(
        r'(Figure\s+\d+[-–]\d+)', re.IGNORECASE
    )
    # Pattern for standalone caption lines: "Figure X-Y  Caption Text Here"
    caption_pattern = re.compile(
        r'^(Figure\s+\d+[-–]\d+)\s+([A-Z][\w\s,\-/()\']+)', re.IGNORECASE
    )

    # First pass: collect best description per figure from caption lines
    for line in lines:
        cap_match = caption_pattern.match(line.strip())
        if cap_match:
            fig_key = re.sub(r'\s+', ' ', cap_match.group(1)).strip()
            desc = cap_match.group(2).strip().rstrip('.')
            if desc and len(desc) > 5:
                seen_figures[fig_key] = desc

    # Second pass: collect from context if not found in captions
    for idx, line in enumerate(lines):
        matches = figure_pattern.findall(line)
        for raw_ref in matches:
            fig_key = re.sub(r'\s+', ' ', raw_ref).strip()
            if fig_key in seen_figures:
                continue
            # Gather context: surrounding text for description
            context_parts = []
            for j in range(idx + 1, min(idx + 4, len(lines))):
                stripped = lines[j].strip()
                if stripped and not figure_pattern.search(stripped):
                    context_parts.append(stripped)
                else:
                    break
            context = ' '.join(context_parts)
            if context and len(context) > 10:
                seen_figures[fig_key] = context[:200]

    # Third pass: emit placeholders (one per figure, at first caption line)
    emitted = set()
    i = 0
    while i < len(lines):
        line = lines[i]
        cap_match = caption_pattern.match(line.strip())
        if cap_match:
            fig_key = re.sub(r'\s+', ' ', cap_match.group(1)).strip()
            if fig_key not in emitted:
                desc = seen_figures.get(fig_key, '')
                if desc:
                    result.append(
                        f'\n<!-- DIAGRAM: {fig_key} - {desc} -->\n'
                    )
                else:
                    result.append(f'\n<!-- DIAGRAM: {fig_key} -->\n')
                emitted.add(fig_key)
        else:
            result.append(line)
        i += 1

    return '\n'.join(result)


def build_chapter_md(chapter_name, pages_text):
    """Build a markdown file from extracted pages."""
    combined = '\n\n'.join(text for _, text in pages_text)
    combined = insert_diagram_placeholders(combined)

    # Clean up common PDF artifacts
    combined = re.sub(r'\n{3,}', '\n\n', combined)
    combined = re.sub(r'[ \t]+\n', '\n', combined)

    return f"# {chapter_name}\n\n{combined}"


def build_skill_md(skill_name, description, layers):
    """Build the SKILL.md with teaching rules and chapter index."""
    layer_table = ""
    for layer in layers:
        files = ', '.join(f"`{f}`" for f in layer['files'])
        layer_table += f"| {layer['name']} | {layer['chapters']} | {files} |\n"

    return f"""---
name: {skill_name}
description: {description}
version: 1.0
---

# {skill_name}

## Teaching Rules

When teaching content from any chapter:
- Auto-generate ASCII or Mermaid diagrams for any concept that would
  normally have a visual (topologies, packet flows, protocol exchanges,
  decision trees, architecture diagrams)
- When you encounter a `<!-- DIAGRAM: ... -->` placeholder, reconstruct
  the diagram using ASCII art for network topologies or Mermaid for
  flowcharts/sequences/state diagrams
- Use 2-3 bullets max, then diagram, then explanation
- Mark Anki-worthy Q/A pairs at the end of each teaching block
- Spell out every acronym on first use

## Layers

| Layer | Chapters | Reference Files |
|-------|----------|-----------------|
{layer_table}
"""


def process_config(config_path):
    """Process a config file and build skill zips."""
    with open(config_path) as f:
        config = json.load(f)

    output_dir = Path(config.get('output_dir', 'D:/'))
    skill_prefix = config.get('skill_prefix', 'SKILL')

    for layer in config['layers']:
        layer_name = layer['name']
        layer_slug = layer['slug']
        pdf_path = layer['pdf']
        chapters = layer['chapters']

        print(f"=== Processing: {layer_name} ===")

        # Extract text for each chapter in this layer
        all_files = []
        for ch in chapters:
            ch_name = ch['name']
            ch_slug = ch['slug']
            start_page = ch.get('start_page')
            end_page = ch.get('end_page')

            print(f"  Extracting: {ch_name} (pages {start_page}-{end_page})")
            pages = extract_text_from_pdf(pdf_path, start_page, end_page)

            if not pages:
                print(f"  WARNING: No text extracted for {ch_name}")
                continue

            md_content = build_chapter_md(ch_name, pages)
            all_files.append((f"{ch_slug}.md", md_content))

        if not all_files:
            print(f"  SKIPPED: No content for {layer_name}")
            continue

        # Build SKILL.md for this layer
        layer_info = [{
            'name': layer_name,
            'chapters': ', '.join(ch['name'] for ch in chapters),
            'files': [f for f, _ in all_files]
        }]

        skill_md = build_skill_md(
            f"{skill_prefix}-{layer_name}",
            layer.get('description', f'Reference for {layer_name}'),
            layer_info
        )

        # Build zip
        zip_name = f"{skill_prefix}-{layer_slug}-claude.zip"
        zip_path = output_dir / zip_name
        folder_name = f"{skill_prefix}-{layer_slug}"

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"{folder_name}/SKILL.md", skill_md)
            for filename, content in all_files:
                zf.writestr(f"{folder_name}/references/{filename}", content)

        file_count = len(all_files) + 1
        print(f"  Built: {zip_path} ({file_count} files)")

    print("\n=== All layers complete ===")


def generate_config_from_toc(pdf_paths, output_path="config.json"):
    """Helper: generate a starter config from PDF table of contents."""
    config = {
        "skill_prefix": "SKILL",
        "output_dir": "D:/",
        "layers": []
    }

    for pdf_path in pdf_paths:
        print(f"\n=== TOC: {pdf_path} ===")
        toc = get_toc(pdf_path)
        for level, title, page in toc:
            if level <= 2:
                indent = '  ' * (level - 1)
                print(f"{indent}p.{page:>4} | {title}")

    print(f"\nUse the TOC above to fill in config.json with page ranges.")
    print(f"Template written to: {output_path}")

    with open(output_path, 'w') as f:
        json.dump(config, f, indent=2)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python book_to_skill_lite.py config.json        # Build skills from config")
        print("  python book_to_skill_lite.py --toc file.pdf ...  # Print TOC to plan config")
        sys.exit(1)

    if sys.argv[1] == '--toc':
        generate_config_from_toc(sys.argv[2:])
    else:
        process_config(sys.argv[1])
