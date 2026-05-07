"""HTML/PDF export helpers for the migrated export module."""

import asyncio
from html import escape
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape
import pyppeteer
from ebooklib import epub
from html import escape

from core.schema.document import DocumentRoot


class PDFGenerator:
    """Render publication HTML from document models and templates."""

    def __init__(self, template_dir: Optional[str] = None):
        self.template_dir = Path(template_dir) if template_dir else Path("assets/templates")
        self.environment = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(("html", "xml")),
        )

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        template = self.environment.get_template(template_name)
        return template.render(**context)

    def render_document_html(self, document: DocumentRoot, title: str = "Untitled") -> str:
        """Render a complete HTML document from a validated DocumentRoot."""
        chapter_html = "\n".join(self._render_chapter(chapter) for chapter in document.children)
        return "\n".join(
            [
                "<!doctype html>",
                '<html lang="en">',
                "<head>",
                '  <meta charset="utf-8">',
                f"  <title>{escape(title)}</title>",
                "  <style>",
                "    body { font-family: serif; line-height: 1.6; margin: 2rem; }",
                "    .chapter { break-before: page; }",
                "    .multilingual-block { margin: 1rem 0; }",
                "    .lang { margin: 0.25rem 0; }",
                "    .rtl { direction: rtl; text-align: right; }",
                "    .interlinear { display: flex; flex-wrap: wrap; gap: 0.75rem; margin: 1rem 0; }",
                "    .token { display: inline-flex; flex-direction: column; align-items: center; }",
                "    .token-source { font-weight: bold; }",
                "    .footnote { font-size: 0.9em; border-top: 1px solid #ddd; margin-top: 1rem; }",
                "  </style>",
                "</head>",
                "<body>",
                chapter_html,
                "</body>",
                "</html>",
            ]
        )

    def _render_chapter(self, chapter) -> str:
        blocks = "\n".join(self._render_block(block) for block in chapter.children)
        return "\n".join(
            [
                '<section class="chapter">',
                f"  <h1>{escape(chapter.title)}</h1>",
                blocks,
                "</section>",
            ]
        )

    def _render_block(self, block) -> str:
        if block.type == "paragraph":
            return f'  <p>{escape(block.text)}</p>'
        if block.type == "footnote":
            return f'  <aside class="footnote">{escape(block.content)}</aside>'
        if block.type == "multilingual_block":
            return self._render_multilingual_block(block)
        if block.type == "interlinear_block":
            return self._render_interlinear_block(block)
        if block.type == "math_block":
            return f'  <div class="math">{escape(block.latex_syntax)}</div>'
        if block.type == "canvas_block":
            return '  <div class="canvas-placeholder"></div>'
        return ""

    def _render_multilingual_block(self, block) -> str:
        parts = ['  <div class="multilingual-block">']
        for code, text in [
            ("ar", block.ar or ""),
            ("ur", block.ur or ""),
            ("gu", block.gu or ""),
            ("en", block.en or ""),
        ]:
            if not text:
                continue
            direction_class = " rtl" if code in {"ar", "ur"} else ""
            parts.append(
                f'    <p class="lang lang-{code}{direction_class}" lang="{code}">'
                f"{escape(text)}</p>"
            )
        parts.append("  </div>")
        return "\n".join(parts)

    def _render_interlinear_block(self, block) -> str:
        parts = ['  <div class="interlinear">']
        for token in block.tokens:
            parts.extend(
                [
                    '    <span class="token">',
                    f'      <bdi class="token-source">{escape(token.source_l1)}</bdi>',
                    f'      <span class="token-translit">{escape(token.transliteration_l2)}</span>',
                    f'      <span class="token-translation">{escape(token.translation_l3)}</span>',
                    "    </span>",
                ]
            )
        parts.append("  </div>")
        return "\n".join(parts)

    async def export_pdf_async(self, html_content: str, output_path: Path, 
                              page_format: str = "A4", margin_mm: int = 20) -> Path:
        """Export HTML content to PDF using headless Chromium via pyppeteer."""
        browser = await pyppeteer.launch()
        page = await browser.newPage()
        
        # Set page format and margins
        width, height = self._get_page_dimensions(page_format)
        margin_px = margin_mm * 3.78  # Convert mm to pixels (96 DPI)
        
        await page.setViewport({
            'width': int(width),
            'height': int(height),
            'deviceScaleFactor': 1,
        })
        
        await page.setContent(html_content)
        
        # Wait for fonts and styles to load
        await page.waitFor(100)
        
        # Generate PDF
        await page.pdf({
            'path': str(output_path),
            'format': page_format.lower(),
            'margin': {
                'top': f'{margin_mm}mm',
                'right': f'{margin_mm}mm', 
                'bottom': f'{margin_mm}mm',
                'left': f'{margin_mm}mm'
            },
            'printBackground': True,
            'preferCSSPageSize': True,
        })
        
        await browser.close()
        return output_path

    def export_pdf(self, html_content: str, output_path: Path,
                  page_format: str = "A4", margin_mm: int = 20) -> Path:
        """Synchronous wrapper for PDF export."""
        return asyncio.run(self.export_pdf_async(html_content, output_path, page_format, margin_mm))

    @staticmethod
    def _get_page_dimensions(page_format: str) -> tuple[float, float]:
        """Get page dimensions in pixels for the given format."""
        # Standard page sizes in mm (converted to pixels at 96 DPI)
        sizes = {
            'a4': (210, 297),
            'letter': (216, 279),
            'a3': (297, 420),
            'a5': (148, 210),
        }
        width_mm, height_mm = sizes.get(page_format.lower(), sizes['a4'])
        # Convert mm to pixels (96 DPI)
        return width_mm * 3.78, height_mm * 3.78

    def _render_chapter_epub(self, chapter) -> str:
        """Render a chapter to HTML for EPUB."""
        content = []
        
        for block in chapter.children:
            if block.type == "paragraph":
                content.append(f"<p>{escape(block.text)}</p>")
            elif block.type == "footnote":
                content.append(f"<div class=\"footnote\">{escape(block.content)}</div>")
            elif block.type == "multilingual_block":
                content.append("<div class=\"multilingual-block\">")
                for code, text in [
                    ("ar", block.ar or ""),
                    ("ur", block.ur or ""),
                    ("gu", block.gu or ""),
                    ("en", block.en or ""),
                ]:
                    if text:
                        lang_class = "rtl" if code in ["ar", "ur", "gu"] else ""
                        content.append(f"<div class=\"lang {lang_class}\"><strong>{code.upper()}:</strong> {escape(text)}</div>")
                content.append("</div>")
            elif block.type == "interlinear_block":
                content.append("<div class=\"interlinear\">")
                for token in block.tokens:
                    content.append(f"<div class=\"token\"><span class=\"token-source\">{escape(token.source_l1)}</span><span>{escape(token.transliteration_l2)}</span><span>{escape(token.translation_l3)}</span></div>")
                content.append("</div>")
            elif block.type == "math_block":
                content.append(f"<div class=\"math\">$${escape(block.latex_syntax)}$$</div>")
            elif block.type == "canvas_block":
                content.append("<div class=\"canvas\">[Vector graphics]</div>")
        
        return "\n".join(content)

    def export_epub(self, document: DocumentRoot, output_path: Path, title: str = "Untitled") -> Path:
        """Export document to EPUB format."""
        book = epub.EpubBook()
        
        # Set metadata
        book.set_identifier(f"maktaba-{document.id}")
        book.set_title(title)
        book.set_language("en")
        book.add_author("Maktaba-OS")
        
        # Create chapters
        chapters = []
        toc = []
        
        for i, chapter in enumerate(document.children):
            # Generate HTML content for chapter
            chapter_html = self._render_chapter_epub(chapter)
            full_html = f"""
            <html>
            <head>
                <title>{escape(chapter.title)}</title>
                <style>
                    body {{ font-family: serif; line-height: 1.6; margin: 5%; }}
                    .chapter {{ break-before: page; }}
                    .multilingual-block {{ margin: 1rem 0; }}
                    .lang {{ margin: 0.25rem 0; }}
                    .rtl {{ direction: rtl; text-align: right; }}
                    .interlinear {{ display: flex; flex-wrap: wrap; gap: 0.75rem; margin: 1rem 0; }}
                    .token {{ display: inline-flex; flex-direction: column; align-items: center; }}
                    .token-source {{ font-weight: bold; }}
                    .footnote {{ font-size: 0.9em; border-top: 1px solid #ddd; margin-top: 1rem; }}
                </style>
            </head>
            <body>
                {chapter_html}
            </body>
            </html>
            """
            
            # Create EPUB chapter
            epub_chapter = epub.EpubHtml(
                title=chapter.title,
                file_name=f"chap_{i+1}.xhtml",
                content=full_html
            )
            book.add_item(epub_chapter)
            chapters.append(epub_chapter)
            toc.append(epub_chapter)
        
        # Add navigation
        book.toc = tuple(toc)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        
        # Define spine
        book.spine = ["nav"] + chapters
        
        # Write EPUB file
        epub.write_epub(str(output_path), book)
        return output_path

    def export_markdown(self, document: DocumentRoot, output_path: Path) -> Path:
        """Export document to Markdown format."""
        content = []
        
        for chapter in document.children:
            content.append(f"# {chapter.title}\n")
            
            for block in chapter.children:
                if block.type == "paragraph":
                    content.append(f"{block.text}\n\n")
                elif block.type == "footnote":
                    content.append(f"*{block.content}*\n\n")
                elif block.type == "multilingual_block":
                    for code, text in [
                        ("ar", block.ar or ""),
                        ("ur", block.ur or ""),
                        ("gu", block.gu or ""),
                        ("en", block.en or ""),
                    ]:
                        if text:
                            lang_name = {"ar": "Arabic", "ur": "Urdu", "gu": "Gujarati", "en": "English"}.get(code, code.upper())
                            content.append(f"**{lang_name}:** {text}\n\n")
                elif block.type == "interlinear_block":
                    content.append("**Interlinear:**\n")
                    for token in block.tokens:
                        content.append(f"- {token.source_l1} → {token.transliteration_l2} → {token.translation_l3}\n")
                    content.append("\n")
                elif block.type == "math_block":
                    content.append(f"$$$\n{block.latex_syntax}\n$$$\n\n")
                elif block.type == "canvas_block":
                    content.append("*[Vector graphics placeholder]*\n\n")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("".join(content))
        
        return output_path
