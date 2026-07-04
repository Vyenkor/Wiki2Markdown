from __future__ import annotations

import argparse
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urljoin, urlparse

import requests
import tkinter as tk
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
from markdownify import markdownify as html_to_markdown
from tkinter import filedialog, messagebox

try:
    from opencc import OpenCC
except ImportError:
    OpenCC = None


APP_TITLE = "Wiki2Markdown"
DEFAULT_OUTPUT_DIR = "output"
USER_AGENT = "Wiki2Markdown/2.0 (https://github.com/Vyenkor/Wiki2Markdown)"

MEDIA_PREFIXES = (
    "File:",
    "Image:",
    "Category:",
    "Help:",
    "Special:",
    "Wikipedia:",
    "Portal:",
    "Template:",
)

NOISE_SELECTORS = (
    "script",
    "style",
    "noscript",
    "form",
    "input",
    "button",
    "nav",
    "#toc",
    ".toc",
    ".vector-toc",
    ".mw-editsection",
    ".mw-jump-link",
    ".mw-indicators",
    ".noprint",
    ".nomobile",
    ".metadata",
    ".ambox",
    ".tmbox",
    ".cmbox",
    ".ombox",
    ".fmbox",
    ".hatnote",
    ".navbox",
    ".navbar",
    ".vertical-navbox",
    ".sidebar",
    ".portal",
    ".sistersitebox",
    ".printfooter",
    ".catlinks",
)

NAVIGATION_TEXTS = {
    "首页",
    "主页",
    "返回",
    "回到首页",
    "上一页",
    "下一页",
    "main page",
    "home",
    "back",
    "previous",
    "next",
}


@dataclass(frozen=True)
class WikiPage:
    title: str
    html: str
    base_url: str


@dataclass(frozen=True)
class ExportOptions:
    source: str
    mode: str = "title"
    lang: str = "zh"
    output_dir: Path = Path(DEFAULT_OUTPUT_DIR)
    download_images: bool = True
    convert_chinese: bool = True


@dataclass(frozen=True)
class ExportResult:
    title: str
    markdown_path: Path
    image_count: int


class WikiExportError(RuntimeError):
    pass


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def safe_filename(value: str, fallback: str = "wiki-page") -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")
    value = re.sub(r"\s+", " ", value)
    return value or fallback


def fetch_page(source: str, mode: str, lang: str, session: requests.Session | None = None) -> WikiPage:
    session = session or make_session()
    if mode == "title":
        return fetch_page_by_title(source, lang, session)
    if mode == "url":
        return fetch_page_by_url(source, session)
    raise ValueError(f"Unknown mode: {mode}")


def fetch_page_by_title(title: str, lang: str, session: requests.Session) -> WikiPage:
    api_url = f"https://{lang}.wikipedia.org/w/api.php"
    response = session.get(
        api_url,
        params={
            "action": "parse",
            "page": title,
            "prop": "text|displaytitle",
            "format": "json",
            "redirects": "1",
            "disableeditsection": "1",
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        info = data["error"].get("info", "Unknown MediaWiki error")
        raise WikiExportError(info)

    parsed = data.get("parse", {})
    page_title = BeautifulSoup(parsed.get("displaytitle") or title, "html.parser").get_text("", strip=True)
    html = parsed.get("text", {}).get("*", "")
    if not html:
        raise WikiExportError("Wikipedia returned an empty page.")
    return WikiPage(title=page_title, html=html, base_url=f"https://{lang}.wikipedia.org")


def fetch_page_by_url(url: str, session: requests.Session) -> WikiPage:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    heading = soup.select_one("#firstHeading") or soup.select_one("h1")
    content = soup.select_one("#mw-content-text .mw-parser-output") or soup.select_one("#bodyContent")
    if not heading or not content:
        raise WikiExportError("Could not find the article title or content on this page.")
    return WikiPage(title=heading.get_text(" ", strip=True), html=str(content), base_url=url)


def convert_page_to_markdown(page: WikiPage, options: ExportOptions, session: requests.Session | None = None) -> ExportResult:
    session = session or make_session()
    soup = BeautifulSoup(page.html, "html.parser")
    content = find_article_content(soup)
    remove_noise(content)
    normalize_references(content)
    image_count = localize_images(content, page, options, session) if options.download_images else 0
    convert_internal_links(content, page.base_url)

    markdown = html_to_markdown(str(content), heading_style="ATX", bullets="-")
    markdown = post_process_markdown(markdown, page.title, options)

    output_dir = Path(options.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = output_dir / f"{safe_filename(page.title)}.md"
    markdown_path.write_text(markdown, encoding="utf-8")
    return ExportResult(title=page.title, markdown_path=markdown_path, image_count=image_count)


def find_article_content(soup: BeautifulSoup) -> Tag:
    content = soup.select_one(".mw-parser-output") or soup.select_one("#mw-content-text") or soup
    if isinstance(content, BeautifulSoup):
        wrapper = soup.new_tag("div")
        for child in list(soup.contents):
            wrapper.append(child.extract())
        return wrapper
    return content


def remove_noise(content: Tag) -> None:
    for selector in NOISE_SELECTORS:
        for node in content.select(selector):
            node.decompose()

    for node in list(content.find_all(True)):
        if not isinstance(node, Tag):
            continue
        role = (node.get("role") or "").lower()
        classes = " ".join(node.get("class", [])).lower()
        if role == "navigation" or "navigation" in classes:
            node.decompose()
            continue
        if node.get_text(" ", strip=True).lower() in NAVIGATION_TEXTS:
            node.decompose()


def normalize_references(content: Tag) -> None:
    for sup in content.select("sup.reference"):
        text = sup.get_text(" ", strip=True)
        match = re.search(r"\d+", text)
        if match:
            sup.replace_with(NavigableString(f"$^{{{match.group(0)}}}$"))
        else:
            sup.decompose()


def localize_images(content: Tag, page: WikiPage, options: ExportOptions, session: requests.Session) -> int:
    image_dir = Path(options.output_dir) / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    count = 0

    for img in list(content.find_all("img")):
        if should_skip_image(img):
            img.decompose()
            continue

        src = img.get("src") or img.get("data-src")
        if not src:
            img.decompose()
            continue

        image_url = urljoin(page.base_url, src)
        count += 1
        filename = build_image_filename(page.title, count, image_url)
        target_path = image_dir / filename

        try:
            response = session.get(image_url, timeout=30)
            response.raise_for_status()
            target_path.write_bytes(response.content)
        except requests.RequestException:
            count -= 1
            img.decompose()
            continue

        # Keep image embeds pipe-free so they do not split Markdown table cells.
        img.replace_with(NavigableString(f"\n![[images/{filename}]]\n"))

    return count


def should_skip_image(img: Tag) -> bool:
    src = (img.get("src") or img.get("data-src") or "").lower()
    classes = " ".join(img.get("class", [])).lower()
    width = parse_int(img.get("width"))
    height = parse_int(img.get("height"))
    if "mw-file-element" not in classes and width and height and (width < 40 or height < 40):
        return True
    return any(token in src for token in ("oojs_ui_icon", "wikimedia-button", "poweredby_mediawiki"))


def parse_int(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def build_image_filename(title: str, index: int, image_url: str) -> str:
    path = urlparse(image_url).path
    ext = Path(path).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}:
        ext = ".jpg"
    return f"{safe_filename(title)}_{index:03d}{ext}"


def convert_internal_links(content: Tag, base_url: str) -> None:
    for link in list(content.find_all("a")):
        href = link.get("href") or ""
        label = link.get_text(" ", strip=True)
        if not label:
            link.decompose()
            continue

        if href.startswith("#"):
            link.replace_with(NavigableString(label))
            continue

        if is_wiki_article_link(href, base_url):
            target = wiki_target_from_href(href)
            if target:
                if any(target.startswith(prefix) for prefix in MEDIA_PREFIXES):
                    link.replace_with(NavigableString(label))
                elif target == label:
                    link.replace_with(NavigableString(f"[[{target}]]"))
                else:
                    link.replace_with(NavigableString(f"[[{target}|{label}]]"))
            continue

        if "redlink=1" in href:
            link.replace_with(NavigableString(label))


def is_wiki_article_link(href: str, base_url: str) -> bool:
    absolute = urljoin(base_url, href)
    parsed = urlparse(absolute)
    return parsed.path.startswith("/wiki/")


def wiki_target_from_href(href: str) -> str:
    path = urlparse(href).path
    if "/wiki/" not in path:
        return ""
    target = path.split("/wiki/", 1)[1]
    return unquote(target).replace("_", " ").strip()


def post_process_markdown(markdown: str, title: str, options: ExportOptions) -> str:
    markdown = markdown.replace("\\[\\[", "[[").replace("\\]\\]", "]]")
    markdown = restore_non_table_wikilink_pipes(markdown)
    markdown = markdown.replace("\\_", "_")
    markdown = re.sub(r"\[\[?(\d+)\]?\]\(#cite_note-[^)]+\)", r"$^{\1}$", markdown)
    markdown = re.sub(r"\[([^\]]+)\]\(#[^)]+\)", r"\1", markdown)
    markdown = re.sub(r"\[编辑\]|\[edit\]", "", markdown, flags=re.IGNORECASE)
    markdown = remove_standalone_navigation_lines(markdown)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()

    if options.lang == "zh" and options.convert_chinese and OpenCC is not None:
        markdown = OpenCC("t2s").convert(markdown)

    return f"# {title}\n\n{markdown}\n"


def restore_non_table_wikilink_pipes(markdown: str) -> str:
    lines: list[str] = []
    for line in markdown.splitlines():
        if is_markdown_table_line(line):
            lines.append(escape_table_wikilink_pipes(line))
        else:
            lines.append(line.replace("\\|", "|"))
    return "\n".join(lines)


def escape_table_wikilink_pipes(line: str) -> str:
    def escape_match(match: re.Match[str]) -> str:
        text = match.group(0)
        prefix = "![[" if text.startswith("![[") else "[["
        inner = text[len(prefix):-2].replace("\\|", "|")
        escaped_inner = inner.replace("|", "\\|")
        return f"{prefix}{escaped_inner}]]"

    return re.sub(r"!?\[\[[^\]\n]+?\]\]", escape_match, line)


def is_markdown_table_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or "|" not in stripped:
        return False
    if re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", stripped):
        return True
    return stripped.startswith("|") or stripped.endswith("|") or stripped.count("|") >= 2


def remove_standalone_navigation_lines(markdown: str) -> str:
    cleaned: list[str] = []
    for line in markdown.splitlines():
        compact = re.sub(r"[*_`\[\]\(\)#\s]+", "", line).lower()
        if compact in NAVIGATION_TEXTS:
            continue
        cleaned.append(line.rstrip())
    return "\n".join(cleaned)


def export_wiki_article(options: ExportOptions) -> ExportResult:
    session = make_session()
    page = fetch_page(options.source, options.mode, options.lang, session)
    return convert_page_to_markdown(page, options, session)


def create_gui() -> tk.Tk:
    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("620x340")
    root.resizable(False, False)

    source_var = tk.StringVar()
    mode_var = tk.StringVar(value="title")
    lang_var = tk.StringVar(value="zh")
    output_var = tk.StringVar(value=str(Path(DEFAULT_OUTPUT_DIR).resolve()))
    images_var = tk.BooleanVar(value=True)
    status_var = tk.StringVar(value="准备导出维基百科文章。")

    frame = tk.Frame(root, padx=18, pady=16)
    frame.pack(fill=tk.BOTH, expand=True)

    tk.Label(frame, text="来源：").grid(row=0, column=0, sticky="e", pady=8)
    tk.Entry(frame, textvariable=source_var, width=58).grid(row=0, column=1, columnspan=3, sticky="w", pady=8)

    tk.Label(frame, text="模式：").grid(row=1, column=0, sticky="e", pady=8)
    tk.Radiobutton(frame, text="按词条", variable=mode_var, value="title").grid(row=1, column=1, sticky="w")
    tk.Radiobutton(frame, text="按 URL", variable=mode_var, value="url").grid(row=1, column=2, sticky="w")

    tk.Label(frame, text="语言：").grid(row=2, column=0, sticky="e", pady=8)
    tk.Radiobutton(frame, text="中文", variable=lang_var, value="zh").grid(row=2, column=1, sticky="w")
    tk.Radiobutton(frame, text="English", variable=lang_var, value="en").grid(row=2, column=2, sticky="w")

    tk.Label(frame, text="输出目录：").grid(row=3, column=0, sticky="e", pady=8)
    tk.Entry(frame, textvariable=output_var, width=45).grid(row=3, column=1, columnspan=2, sticky="w", pady=8)

    def choose_output_dir() -> None:
        selected = filedialog.askdirectory(initialdir=output_var.get() or os.getcwd())
        if selected:
            output_var.set(selected)

    tk.Button(frame, text="选择", command=choose_output_dir).grid(row=3, column=3, sticky="w", padx=6)
    tk.Checkbutton(frame, text="下载并嵌入图片", variable=images_var).grid(row=4, column=1, columnspan=2, sticky="w", pady=8)

    export_button = tk.Button(frame, text="开始导出", width=14)
    export_button.grid(row=5, column=1, pady=14, sticky="w")

    status_label = tk.Label(frame, textvariable=status_var, wraplength=560, justify="left", anchor="w")
    status_label.grid(row=6, column=0, columnspan=4, sticky="we", pady=8)

    def set_busy(is_busy: bool) -> None:
        export_button.config(state=tk.DISABLED if is_busy else tk.NORMAL)

    def run_from_gui() -> None:
        source = source_var.get().strip()
        if not source:
            messagebox.showwarning("缺少来源", "请输入维基百科词条或页面 URL。")
            return

        options = ExportOptions(
            source=source,
            mode=mode_var.get(),
            lang=lang_var.get(),
            output_dir=Path(output_var.get()),
            download_images=images_var.get(),
        )
        set_busy(True)
        status_var.set("正在抓取和转换，请稍候...")

        def worker() -> None:
            try:
                result = export_wiki_article(options)
                message = f"完成：{result.markdown_path}，图片 {result.image_count} 张"
            except Exception as exc:
                message = f"失败：{exc}"
            root.after(0, lambda: (status_var.set(message), set_busy(False)))

        threading.Thread(target=worker, daemon=True).start()

    export_button.config(command=run_from_gui)
    return root


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export Wikipedia articles to Obsidian-friendly Markdown.")
    parser.add_argument("source", nargs="?", help="Wikipedia title or full page URL.")
    parser.add_argument("--mode", choices=("title", "url"), default="title", help="How to read source.")
    parser.add_argument("--lang", default="zh", help="Wikipedia language code, for example zh or en.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR, help="Output directory.")
    parser.add_argument("--no-images", action="store_true", help="Do not download article images.")
    parser.add_argument("--gui", action="store_true", help="Open the desktop GUI.")
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if args.gui or not args.source:
        create_gui().mainloop()
        return 0

    result = export_wiki_article(
        ExportOptions(
            source=args.source,
            mode=args.mode,
            lang=args.lang,
            output_dir=Path(args.output),
            download_images=not args.no_images,
        )
    )
    print(f"Exported {result.title} -> {result.markdown_path}")
    print(f"Images downloaded: {result.image_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
