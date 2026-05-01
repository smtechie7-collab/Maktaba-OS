from core.schema.document import InterlinearToken
from modules.interlinear import TokenAligner


def test_arabic_alignment_keeps_words_and_punctuation():
    aligner = TokenAligner()

    tokens = aligner.align_text("بسم الله.", "In name.")

    assert [token.source_l1 for token in tokens] == ["بسم", "الله", "."]
    assert [token.translation_l3 for token in tokens] == ["In", "name", "."]
    assert tokens[0].transliteration_l2 == "bsm"


def test_urdu_alignment_and_transliteration():
    aligner = TokenAligner()

    tokens = aligner.align_text("اللہ کے نام", "Allah name", source_lang="ur")

    assert [token.source_l1 for token in tokens][:2] == ["اللہ", "کے"]
    assert tokens[0].transliteration_l2


def test_manual_alignment_uses_requested_pairs():
    aligner = TokenAligner()

    tokens = aligner.manual_align(
        ["بسم", "الله"],
        ["In", "Allah"],
        [(0, 1), (1, 0)],
    )

    assert [(token.source_l1, token.translation_l3) for token in tokens] == [
        ("بسم", "Allah"),
        ("الله", "In"),
    ]


def test_validation_reports_empty_and_long_translations():
    aligner = TokenAligner()
    tokens = [
        InterlinearToken(source_l1="", transliteration_l2="", translation_l3=""),
        InterlinearToken(
            source_l1="الله",
            transliteration_l2="allah",
            translation_l3="a very long token translation",
        ),
    ]

    warnings = aligner.validate_alignment(tokens)

    assert "1 tokens have empty source text" in warnings
    assert "1 tokens have empty translations" in warnings
    assert "1 tokens have unusually long translations" in warnings
