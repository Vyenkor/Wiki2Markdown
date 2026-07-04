# Wiki2Markdown

Wiki2Markdown 是一个把维基百科文章导出为 Obsidian 友好 Markdown 的小工具。

## 主要功能

- 支持按词条名抓取，也支持直接输入维基百科页面 URL。
- 将维基百科 HTML 正文转换为 Markdown。
- 将维基内部文章链接转换为 Obsidian 双链，例如 `[[Apple|苹果]]`。
- 下载正文图片到 `output/images/`，并写成 Obsidian 嵌入格式，例如 `![[images/词条_001.jpg]]`。
- 将脚注引用转换为 `$^{1}$` 这种 Markdown/Obsidian 可读格式。
- 清理编辑按钮、目录、导航框、提示框、分类链接、打印页脚等杂乱信息。
- 中文页面默认进行繁体转简体。
- 提供 GUI 和命令行两种使用方式。

## 环境要求

- Python 3.10+ 推荐，Python 3.9+ 通常也可运行。
- Windows 自带的 `tkinter` 用于 GUI。
- 网络连接，用于访问维基百科和下载图片。

## 一键安装依赖

双击运行：

```bat
install_dependencies.bat
```

或在 PowerShell 中运行：

```powershell
.\scripts\install_dependencies.ps1
```

依赖列表在 `requirements.txt`：

- `beautifulsoup4`
- `markdownify`
- `opencc-python-reimplemented`
- `requests`

## 使用方式

打开 GUI：

```bash
python wiki_gui.py
```

或显式打开 GUI：

```bash
python wiki_gui.py --gui
```

命令行按词条导出：

```bash
python wiki_gui.py "人工智能" --lang zh --output output
```

命令行按 URL 导出：

```bash
python wiki_gui.py "https://zh.wikipedia.org/wiki/人工智能" --mode url --lang zh --output output
```

不下载图片：

```bash
python wiki_gui.py "人工智能" --no-images
```

## 输出结果

默认输出到 `output/`：

```text
output/
  人工智能.md
  images/
    人工智能_001.jpg
    人工智能_002.png
```

生成的 Markdown 可以直接放进 Obsidian vault 使用。

## 注意事项

- 维基百科页面结构可能变化，少量复杂模板、表格或参考文献可能仍需要人工整理。
- 同名词条重复导出会覆盖旧的 `.md` 文件。
- SVG、WebP 等图片会按原扩展名保存；如果页面图片地址没有扩展名，会默认保存为 `.jpg`。
