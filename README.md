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
| **Diagram handling** | No special handling | Inserts placeholders - Claude rebuilds as diagrams (format depends on prompt) |
| **Chapter loading** | On-demand (agent skill) | All loaded at once (Claude Desktop zip) |
| **Supported formats** | PDF, EPUB, DOCX, HTML, RTF, MOBI | PDF only |
| **Hosting** | Claude Code, Copilot CLI, Amp, OpenCode | Claude Desktop only |
| **Lab guide support** | No special handling | Cleans artifacts, inserts workflow placeholders for step-by-step procedures |
| **Setup effort** | `git clone` + `/book-to-skill book.pdf` | `--auto` generates config from TOC, or manual page ranges |
| **Best for** | Small-medium books, unlimited tokens | Large books, tight token budget |

### What book-to-skill does better

- **Smarter output.** AI-generated glossaries, pattern files, and cheatsheets. My tool gives you raw text organized into chapters.
- **Format support.** EPUB, DOCX, HTML, RTF, MOBI. I only handle PDF.
- **On-demand loading.** Only reads the chapter you ask about. My zips load everything at once into Claude Desktop's context.
- **Less manual work.** Point it at a file and go. My tool needs a config file (though `--auto` can generate one from the TOC).
- **Multi-agent support.** Works with Claude Code, Copilot CLI, Amp, Hermes, OpenCode. Mine only targets Claude Desktop.

### What this tool does differently

- **Zero token cost.** The whole point. For a large book, that's millions of tokens saved.
- **Diagram placeholders.** When the PDF says "see Figure X-Y", this tool inserts a `<!-- DIAGRAM -->` comment with surrounding context. The SKILL.md teaching rules ask Claude to rebuild these as diagrams, but the actual format (SVG artifact, inline ASCII, table) depends on how you prompt.
- **Workflow placeholders.** Lab guides without Figure references get `<!-- WORKFLOW -->` placeholders instead - procedural step sequences that Claude renders as flowcharts. PDF artifacts (page markers, duplicate headers, footer lines) are cleaned automatically.
- **Auto-config from TOC.** `--auto` reads the PDF table of contents and generates a ready-to-use config. Lab guides with too many TOC entries per section auto-collapse.
- **Build stats.** Every build prints size, line count, and placeholder count per file. Use `--stats` to inspect existing zips.
- **Layer-based splitting.** Groups related chapters into study-session-sized zips (~25-30K tokens). You load only the layer you're studying.
- **Teaching rules in SKILL.md.** Every zip includes instructions telling Claude to auto-generate diagrams, use concise format, and produce Anki-worthy flashcards.

### Honest assessment

If you have the token budget, use [book-to-skill](https://github.com/virgiliojr94/book-to-skill). It produces better output. This tool exists because I needed something that works within constraints. The extraction is dumber but the cost is zero, and the teaching rules + diagram placeholders close some of the quality gap at query time instead of extraction time.

## How it works

```
PDF --> pymupdf extracts text --> auto-detect content type --> placeholders inserted --> markdown per chapter --> zip per layer
                                      |                            |
                                  Textbook?                   Lab guide?
                                  DIAGRAM placeholders        Clean artifacts + WORKFLOW placeholders
```

1. Generate config from TOC (or write manually)
2. Run the script - produces one zip per layer with build stats
3. Upload to Claude Desktop (Settings > Skills)

## Install

```bash
pip install pymupdf
```

## Usage

### Quick start (auto-config)

```bash
# Generate config from PDF table of contents
python book_to_skill_lite.py --auto "path/to/book.pdf"

# Review the generated config.json, then build
python book_to_skill_lite.py config.json
```

### Manual config

```bash
# Print TOC to plan page ranges
python book_to_skill_lite.py --toc "path/to/book.pdf"
```

Then create `config.json` (see `example-config.json`):

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

```bash
python book_to_skill_lite.py config.json
```

### Inspect existing skills

```bash
python book_to_skill_lite.py --stats skill.zip [skill2.zip ...]
```

Output: size, line count, and placeholder count per file.

## Skill zip structure

```
CERT-GUIDE-01-foundations/
  SKILL.md              # Teaching rules (DIAGRAM + WORKFLOW) + chapter index
  references/
    ch01-intro.md       # Extracted text with DIAGRAM or WORKFLOW placeholders
    ch02-basics.md
    ch03-core.md
```

## Content type auto-detection

The tool detects whether a PDF is a textbook or a lab guide and processes accordingly:

| Content type | Detection | Placeholders | Cleanup |
|---|---|---|---|
| Textbook | 3+ `Figure X-Y` references | `<!-- DIAGRAM: Figure X-Y - description -->` | None |
| Lab guide | No `Figure X-Y` references | `<!-- WORKFLOW: task - step1 > step2 > ... -->` | Page markers, duplicate headers, footer lines removed |

## Teaching rules (baked into every SKILL.md)

- Rebuild `<!-- DIAGRAM -->` placeholders as diagrams with standard network device icons
- Rebuild `<!-- WORKFLOW -->` placeholders as step-by-step flowcharts with decision points and expected results
- Also generate diagrams for concepts without placeholders that benefit from a visual
- 2-3 bullets, then diagram, then explanation
- Spell out acronyms on first use

The teaching rules default to SVG artifacts, but Claude's actual output format varies by prompt. Say "use SVG artifacts" to get artifact-panel SVGs, or just "teach me" for whatever format fits the conversation (often inline ASCII or tables).


## License

MIT
