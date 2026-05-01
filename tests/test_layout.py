from core.schema.document import (
    ChapterNode,
    DocumentRoot,
    InterlinearBlock,
    InterlinearToken,
    MultilingualBlock,
    ParagraphNode,
)
from modules.export import PDFGenerator


def test_layout_document_model_supports_multilingual_blocks():
    """Verify migrated layout data is available from the document model."""
    document = DocumentRoot(
        children=[
            ChapterNode(
                title="Chapter 1",
                children=[
                    MultilingualBlock(
                        block_type="paragraph",
                        ar="بسم الله",
                        ur="اللہ کے نام سے",
                    )
                ],
            )
        ]
    )

    assert document.children[0].title == "Chapter 1"
    assert document.children[0].children[0].ar == "بسم الله"


def test_pdf_generator_initialization():
    gen = PDFGenerator(template_dir="assets/templates")
    assert gen.template_dir.as_posix().endswith("assets/templates")


def test_render_document_html_includes_multilingual_content():
    document = DocumentRoot(
        children=[
            ChapterNode(
                title="Opening",
                children=[
                    MultilingualBlock(
                        block_type="paragraph",
                        ar="بسم الله",
                        ur="اللہ کے نام سے",
                        gu="અલ્લાહના નામે",
                        en="In the name of Allah",
                    )
                ],
            )
        ]
    )

    html = PDFGenerator().render_document_html(document, title="Sample")

    assert "<title>Sample</title>" in html
    assert 'class="lang lang-ar rtl"' in html
    assert "بسم الله" in html
    assert "اللہ کے نام سے" in html
    assert "અલ્લાહના નામે" in html
    assert "In the name of Allah" in html


def test_render_document_html_escapes_text():
    document = DocumentRoot(
        children=[
            ChapterNode(
                title="<Opening>",
                children=[ParagraphNode(text="<unsafe>")],
            )
        ]
    )

    html = PDFGenerator().render_document_html(document, title="<Book>")

    assert "<title>&lt;Book&gt;</title>" in html
    assert "<h1>&lt;Opening&gt;</h1>" in html
    assert "<p>&lt;unsafe&gt;</p>" in html


def test_render_document_html_includes_interlinear_tokens():
    document = DocumentRoot(
        children=[
            ChapterNode(
                title="Interlinear",
                children=[
                    InterlinearBlock(
                        tokens=[
                            InterlinearToken(
                                source_l1="بسم",
                                transliteration_l2="bsm",
                                translation_l3="In",
                            )
                        ]
                    )
                ],
            )
        ]
    )

    html = PDFGenerator().render_document_html(document)

    assert 'class="interlinear"' in html
    assert '<bdi class="token-source">بسم</bdi>' in html
    assert "bsm" in html
    assert "In" in html
