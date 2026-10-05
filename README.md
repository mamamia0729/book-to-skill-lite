# book-to-skill-lite

Turn technical books (PDF) into Claude Desktop skills - zero AI tokens for extraction.

Author: Thinh Le

## Why this exists

I needed to turn large technical certification guides into Claude Desktop skills. The existing [book-to-skill](https://github.com/virgiliojr94/book-to-skill) tool is well-built, but it sends the entire book through an AI agent for structuring - that's ~2M+ tokens for a large book. On a limited token budget, that's not practical.

This tool does the extraction with pure Python. Zero AI tokens burned. The tradeoff is real and I want to be upfront about it.

## Comparison with book-to-skill

| Aspect | book-to-skill | book-to-skill-lite |
|--------|--------------|-------------------|
| **Extraction** | AI agent reads and structures | Python (pymupdf) - no AI |
| **Token cost** | ~2M+ for a 5000-page book | Zero |
| **Output quality** | Higher - AI distills key concepts, builds glossary, identifies patterns | Lower - raw text extraction with basic cleanup |
| **Diagram handling** | No special handling | Inserts placeholders with context for Claude to reconstruct |
| **Chapter loading** | On-demand (agent skill) | All loaded at once (Claude Desktop zip) |
| **Supported formats** | PDF, EPUB, DOCX, HTML, RTF, MOBI | PDF only |
| **Hosting** | Claude Code, Copilot CLI, Amp, OpenCode | Claude Desktop only |
| **Setup effort** | `git clone` + `/book-to-skill book.pdf` | Manual config with page ranges |
| **Best for** | Small-medium books, unlimited tokens | Large books, tight token budget |

### What book-to-skill does better

- **Smarter output.** AI-generated glossaries, pattern files, and cheatsheets. My tool gives you raw text organized into chapters.
- **Format support.** EPUB, DOCX, HTML, RTF, MOBI. I only handle PDF.
- **On-demand loading.** Only reads the chapter you ask about. My zips load everything at once into Claude Desktop's context.
- **Less manual work.** Point it at a file and go. My tool needs you to define page ranges in a config file.
- **Multi-agent support.** Works with Claude Code, Copilot CLI, Amp, Hermes, OpenCode. Mine only targets Claude Desktop.

### What this tool does differently

- **Zero token cost.** The whole point. For a large book, that's millions of tokens saved.
- **Diagram placeholders.** When the PDF says "see Figure X-Y", this tool inserts a `<!-- DIAGRAM -->` comment with surrounding context so Claude can reconstruct the visual when teaching.
- **Layer-based splitting.** Groups related chapters into study-session-sized zips (~25-30K tokens). You load only the layer you're studying.
- **Teaching rules in SKILL.md.** Every zip includes instructions telling Claude to auto-generate diagrams, use concise format, and produce Anki-worthy flashcards.

### Honest assessment

If you have the token budget, use [book-to-skill](https://github.com/virgiliojr94/book-to-skill). It produces better output. This tool exists because I needed something that works within constraints. The extraction is dumber but the cost is zero, and the teaching rules + diagram placeholders close some of the quality gap at query time instead of extraction time.

## How it works

```
PDF --> pymupdf extracts text --> diagram placeholders inserted --> markdown per chapter --> zip per layer
```

1. Define layers and page ranges in `config.json`
2. Run the script - produces one zip per layer
3. Upload to Claude Desktop (Settings > Skills)

## Install

```bash
pip install pymupdf
```

## Usage

### Step 1: Print TOC to plan your config

```bash
python book_to_skill_lite.py --toc "path/to/book.pdf"
```

### Step 2: Create config.json

See `example-config.json` for the structure. Map chapters to layers with page ranges from the TOC.

```json
{
  "skill_prefix": "CERT-GUIDE",
  "output_dir": "D:/",
  "layers": [
    {
      "name": "Foundations",
      "slug": "01-foundations",
      "description": "Core concepts and fundamentals",
      "pdf": "path/to/book.pdf",
      "chapters": [
        {
          "name": "Chapter 1 - Introduction",
          "slug": "ch01-intro",
          "start_page": 30,
          "end_page": 75
        }
      ]
    }
  ]
}
```

### Step 3: Build skills

```bash
python book_to_skill_lite.py config.json
```

Output: one zip per layer in `output_dir`, ready for Claude Desktop upload.

## Skill zip structure

```
CERT-GUIDE-01-foundations/
  SKILL.md              # Teaching rules + chapter index
  references/
    ch01-intro.md       # Extracted text with diagram placeholders
    ch02-basics.md
    ch03-core.md
```

## Teaching rules (baked into every SKILL.md)

- Auto-generate ASCII/Mermaid diagrams for any `<!-- DIAGRAM -->` placeholder
- 2-3 bullets, then diagram, then explanation
- Spell out acronyms on first use
- Mark Anki-worthy Q/A pairs at end of each teaching block

## License

MIT
