# Wiki2Markdown

![Wiki2Markdown preview](docs/images/wiki-to-markdown.png)

> Crawl wiki encyclopedia images and articles, then convert wiki articles into Markdown.

Wiki2Markdown exports Wikipedia articles into Markdown that works well in Obsidian. It keeps article images local, removes common page noise, and preserves wiki references as web links so Obsidian does not open empty local notes.

## Features

- Fetch by Wikipedia article title or by full page URL.
- Convert Wikipedia article HTML into Markdown.
- Keep internal wiki article references as web links, for example `[Apple](https://en.wikipedia.org/wiki/Apple)`.
- Download article images to `output/images/` and embed them with Obsidian syntax, for example `![[images/article_001.jpg]]`.
- Convert footnote references into readable Markdown text such as `$^{1}$`.
- Remove edit buttons, tables of contents, navigation boxes, notices, category links, print footers, and other common page clutter.
- Convert Traditional Chinese to Simplified Chinese for Chinese pages by default.
- Provide both GUI and command-line usage.

## Repository Layout

```text
Wiki2Markdown/
  wiki2markdown.py                  # Main GUI and CLI program
  requirements.txt                  # Runtime dependencies
  install_dependencies.bat          # Windows one-click installer
  scripts/
    install_dependencies.ps1        # PowerShell installer
  docs/
    images/
      wiki-to-markdown.png          # README preview image
```

Generated files are written to `output/`, which is ignored by Git.

## Requirements

- Python 3.10+ recommended. Python 3.9+ should usually work.
- `tkinter` for the desktop GUI. It is included with most Windows Python installations.
- Internet access for Wikipedia pages and image downloads.

## Install Dependencies

Double-click on Windows:

```bat
install_dependencies.bat
```

Or run in PowerShell:

```powershell
.\scripts\install_dependencies.ps1
```

The runtime dependencies are listed in `requirements.txt`:

- `beautifulsoup4`
- `markdownify`
- `opencc-python-reimplemented`
- `requests`

## Usage

Open the GUI:

```bash
python wiki2markdown.py
```

Open the GUI explicitly:

```bash
python wiki2markdown.py --gui
```

Export by article title:

```bash
python wiki2markdown.py "Artificial intelligence" --lang en --output output
```

Export a Chinese article:

```bash
python wiki2markdown.py "人工智能" --lang zh --output output
```

Export by full URL:

```bash
python wiki2markdown.py "https://zh.wikipedia.org/wiki/人工智能" --mode url --lang zh --output output
```

Export without downloading images:

```bash
python wiki2markdown.py "Artificial intelligence" --lang en --no-images
```

## Output

Default output structure:

```text
output/
  Artificial intelligence.md
  images/
    Artificial intelligence_001.jpg
    Artificial intelligence_002.png
```

The generated Markdown can be moved directly into an Obsidian vault.

## Notes

- Wikipedia page structures vary. Complex templates, tables, or references may still need manual cleanup.
- Exporting the same article again will overwrite the existing Markdown file with the same title.
- SVG and WebP images are saved with their original extensions. Image URLs without a clear extension are saved as `.jpg`.

## 中文小结

Wiki2Markdown 用来抓取维基百科文章和图片，并导出为适合 Obsidian 使用的 Markdown。程序支持图形界面和命令行，能清理页面杂项、下载图片、转换脚注，并把 wiki 词条引用保留为网页链接，避免 Obsidian 打开空白本地笔记。
