"""HTML/PDF export helpers for the migrated export module."""

from html import escape
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

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
