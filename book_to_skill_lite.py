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
- When you encounter a `<!-- DIAGRAM: ... -->` placeholder, render it as
  an SVG artifact using standard network device icons (router, switch, PC,
  firewall, server, cloud, wireless AP). Use proper shapes, labels, and
  connection lines to reconstruct the original figure
- For concepts without a placeholder that would benefit from a visual,
  also generate an SVG artifact (topologies, packet flows, protocol
  exchanges, decision trees, architecture diagrams)
- Use 2-3 bullets max, then diagram, then explanation
- Spell out every acronym on first use

## Layers

| Layer | Chapters | Reference Files |
|-------|----------|-----------------|
{layer_table}
"""


def print_zip_stats(zip_path):
    """Print size, line count, and diagram placeholder count for a skill zip."""
    with zipfile.ZipFile(zip_path) as zf:
        total_bytes = 0
        total_lines = 0
        total_diagrams = 0
        files = []

        for name in zf.namelist():
            info = zf.getinfo(name)
            total_bytes += info.file_size
            content = zf.read(name).decode('utf-8')
            lines = content.count('\n')
            # Only count real placeholders in reference files, not the
            # template text in SKILL.md
            is_ref = 'references/' in name
            diagrams = len(re.findall(r'<!-- DIAGRAM: .+? -->', content)) if is_ref else 0
            total_lines += lines
            total_diagrams += diagrams
            files.append((name, info.file_size, lines, diagrams))

        print(f"  Stats: {total_bytes:,} bytes | {total_lines:,} lines | {total_diagrams} diagrams")
        for name, size, lines, diagrams in files:
            short = name.split('/')[-1]
            diag_str = f" | {diagrams} diagrams" if diagrams else ""
            print(f"    {size:>8,} bytes  {lines:>5} lines{diag_str}  {short}")


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
        print_zip_stats(zip_path)

    print("\n=== All layers complete ===")


def slugify(title):
    """Turn a title into a filename-safe slug."""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    if len(slug) > 50:
        slug = slug[:50].rsplit('-', 1)[0]
    return slug


def auto_generate_config(pdf_path, output_path="config.json"):
    """Analyze TOC and generate a ready-to-use config with logical layers.

    Groups top-level TOC entries as layers, level-2 entries as chapters.
    Calculates page ranges from consecutive TOC page numbers.
    """
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    toc = doc.get_toc()
    doc.close()

    if not toc:
        print("ERROR: No table of contents found in this PDF.")
        print("Use --toc to inspect the PDF, then create config.json manually.")
        return

    levels = sorted(set(level for level, _, _ in toc))
    layer_level = levels[0]
    chapter_level = levels[1] if len(levels) > 1 else levels[0]

    skip_titles = {
        'cover', 'title', 'copyright', 'dedication', 'acknowledgment',
        'about', 'contents', 'foreword', 'preface', 'icon', 'convention',
        'reader service', 'figure credit', 'halftitle', 'companion',
        'appendix', 'index', 'glossary',
    }

    def is_front_matter(title):
        lower = title.lower()
        return any(skip in lower for skip in skip_titles)

    all_pages = [(level, title, page) for level, title, page in toc]

    layers = []
    current_layer = None

    for idx, (level, title, page) in enumerate(all_pages):
        if level == layer_level:
            if is_front_matter(title):
                continue

            end_page = total_pages
            for future_level, _, future_page in all_pages[idx + 1:]:
                if future_level == layer_level:
                    end_page = future_page - 1
                    break

            current_layer = {
                'name': title.strip(),
                'slug': slugify(title),
                'start_page': page,
                'end_page': end_page,
                'chapters': []
            }
            layers.append(current_layer)

        elif level == chapter_level and current_layer is not None:
            if is_front_matter(title):
                continue

            ch_end = current_layer['end_page']
            for future_level, _, future_page in all_pages[idx + 1:]:
                if future_level <= chapter_level:
                    ch_end = future_page - 1
                    break

            current_layer['chapters'].append({
                'name': title.strip(),
                'slug': slugify(title),
                'start_page': page,
                'end_page': ch_end
            })

    # Flat TOC: each entry is both layer and chapter
    if layer_level == chapter_level:
        for layer in layers:
            if not layer['chapters']:
                layer['chapters'].append({
                    'name': layer['name'],
                    'slug': layer['slug'],
                    'start_page': layer['start_page'],
                    'end_page': layer['end_page']
                })

    # Too many chapters (e.g. lab guides where every screenshot step is a
    # TOC entry): collapse into a single chapter per layer
    max_chapters = 20
    for layer in layers:
        if len(layer['chapters']) > max_chapters:
            first_page = layer['chapters'][0]['start_page']
            last_page = layer['chapters'][-1]['end_page']
            collapsed_count = len(layer['chapters'])
            layer['chapters'] = [{
                'name': layer['name'],
                'slug': layer['slug'],
                'start_page': first_page,
                'end_page': last_page
            }]
            layer['_collapsed'] = collapsed_count

    # Layers with no chapters: treat layer itself as one chapter
    for layer in layers:
        if not layer['chapters']:
            layer['chapters'].append({
                'name': layer['name'],
                'slug': layer['slug'],
                'start_page': layer['start_page'],
                'end_page': layer['end_page']
            })

    pdf_basename = os.path.basename(pdf_path)
    prefix = slugify(os.path.splitext(pdf_basename)[0]).upper()[:20]

    config = {
        "skill_prefix": prefix,
        "output_dir": "D:/",
        "layers": []
    }

    for layer in layers:
        config['layers'].append({
            "name": layer['name'],
            "slug": layer['slug'],
            "description": layer['name'],
            "pdf": pdf_path,
            "chapters": [
                {
                    "name": ch['name'],
                    "slug": ch['slug'],
                    "start_page": ch['start_page'],
                    "end_page": ch['end_page']
                }
                for ch in layer['chapters']
            ]
        })

    with open(output_path, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"\n=== Auto-generated config: {output_path} ===")
    print(f"PDF: {pdf_basename} ({total_pages} pages)")
    print(f"Prefix: {prefix}")
    print(f"Layers: {len(layers)}\n")

    for i, cfg_layer in enumerate(config['layers']):
        ch_count = len(cfg_layer['chapters'])
        first_page = cfg_layer['chapters'][0]['start_page']
        last_page = cfg_layer['chapters'][-1]['end_page']
        collapsed = layers[i].get('_collapsed')
        print(f"  {cfg_layer['name']}")
        if collapsed:
            print(f"    Pages {first_page}-{last_page} | 1 chapter (collapsed from {collapsed} TOC entries)")
        else:
            print(f"    Pages {first_page}-{last_page} | {ch_count} chapter(s)")
        for ch in cfg_layer['chapters']:
            print(f"      {ch['start_page']:>4}-{ch['end_page']:<4} {ch['name']}")
        print()

    print(f"Review {output_path}, then run:")
    print(f"  python book_to_skill_lite.py {output_path}")


def generate_config_from_toc(pdf_paths, output_path="config.json"):
    """Helper: print TOC for manual config planning."""
    for pdf_path in pdf_paths:
        print(f"\n=== TOC: {pdf_path} ===")
        toc = get_toc(pdf_path)
        for level, title, page in toc:
            if level <= 2:
                indent = '  ' * (level - 1)
                print(f"{indent}p.{page:>4} | {title}")

    print(f"\nUse the TOC above to fill in config.json with page ranges.")
    print("Or use --auto to generate config automatically.")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python book_to_skill_lite.py config.json           # Build skills from config")
        print("  python book_to_skill_lite.py --toc file.pdf ...     # Print TOC to plan config")
        print("  python book_to_skill_lite.py --auto file.pdf        # Auto-generate config from TOC")
        print("  python book_to_skill_lite.py --stats file.zip ...   # Show stats for existing zips")
        sys.exit(1)

    if sys.argv[1] == '--toc':
        generate_config_from_toc(sys.argv[2:])
    elif sys.argv[1] == '--auto':
        if len(sys.argv) < 3:
            print("Usage: python book_to_skill_lite.py --auto file.pdf [output.json]")
            sys.exit(1)
        out = sys.argv[3] if len(sys.argv) > 3 else "config.json"
        auto_generate_config(sys.argv[2], out)
    elif sys.argv[1] == '--stats':
        for zp in sys.argv[2:]:
            print(f"\n=== {os.path.basename(zp)} ===")
            print_zip_stats(zp)
    else:
        process_config(sys.argv[1])
