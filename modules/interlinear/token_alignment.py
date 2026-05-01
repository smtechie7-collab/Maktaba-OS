"""
Token alignment helpers for interlinear text.

The implementation is intentionally conservative: it provides deterministic
tokenization, simple 1:1 alignment, manual alignment, and validation hooks.
"""

from typing import List, Tuple
import re

from core.schema.document import InterlinearToken


class TokenAligner:
    """Align source-language tokens with transliteration and translation text."""

    def __init__(self):
        self.alignment_rules = {
            "ar": self._arabic_alignment_rules,
            "ur": self._urdu_alignment_rules,
            "en": self._english_alignment_rules,
        }

    def align_text(
        self,
        source_text: str,
        translation_text: str,
        source_lang: str = "ar",
    ) -> List[InterlinearToken]:
        source_tokens = self._tokenize_text(source_text, source_lang)
        translation_tokens = self._tokenize_text(translation_text, "en")
        return self._align_tokens(source_tokens, translation_tokens, source_lang)

    def _tokenize_text(self, text: str, language: str) -> List[str]:
        if language in self.alignment_rules:
            return self.alignment_rules[language](text)
        return self._english_alignment_rules(text)

    def _arabic_alignment_rules(self, text: str) -> List[str]:
        tokens = re.findall(r"[\u0600-\u06ff\u064b-\u065f\u0670]+|[^\w\s]", text)
        return [token for token in tokens if token.strip()]

    def _urdu_alignment_rules(self, text: str) -> List[str]:
        tokens = re.findall(r"[\u0600-\u06ff\u0750-\u077f]+|[^\w\s]", text)
        return [token for token in tokens if token.strip()]

    def _english_alignment_rules(self, text: str) -> List[str]:
        return re.findall(r"\w+|[^\w\s]", text)

    def _align_tokens(
        self,
        source_tokens: List[str],
        translation_tokens: List[str],
        source_lang: str,
    ) -> List[InterlinearToken]:
        aligned = []
        max_len = max(len(source_tokens), len(translation_tokens))

        for index in range(max_len):
            source = source_tokens[index] if index < len(source_tokens) else ""
            translation = translation_tokens[index] if index < len(translation_tokens) else ""
            transliteration = ""
            if source_lang in ["ar", "ur"] and source:
                transliteration = self._generate_transliteration(source, source_lang)

            aligned.append(
                InterlinearToken(
                    source_l1=source,
                    transliteration_l2=transliteration,
                    translation_l3=translation,
                )
            )

        return aligned

    def _generate_transliteration(self, text: str, language: str) -> str:
        translit_map = {
            "ا": "a",
            "أ": "a",
            "إ": "i",
            "آ": "aa",
            "ب": "b",
            "پ": "p",
            "ت": "t",
            "ث": "th",
            "ج": "j",
            "چ": "ch",
            "ح": "h",
            "خ": "kh",
            "د": "d",
            "ذ": "dh",
            "ر": "r",
            "ڑ": "r",
            "ز": "z",
            "ژ": "zh",
            "س": "s",
            "ش": "sh",
            "ص": "s",
            "ض": "d",
            "ط": "t",
            "ظ": "z",
            "ع": "'",
            "غ": "gh",
            "ف": "f",
            "ق": "q",
            "ك": "k",
            "ک": "k",
            "گ": "g",
            "ل": "l",
            "م": "m",
            "ن": "n",
            "ه": "h",
            "ہ": "h",
            "ھ": "h",
            "و": "w",
            "ی": "y",
            "ي": "y",
            "ے": "e",
            "ء": "'",
            "َ": "a",
            "ُ": "u",
            "ِ": "i",
            "ً": "an",
            "ٌ": "un",
            "ٍ": "in",
            "ْ": "",
            "ّ": "",
            "ٰ": "a",
        }
        return "".join(translit_map.get(char, char) for char in text)

    def manual_align(
        self,
        source_tokens: List[str],
        translation_tokens: List[str],
        alignments: List[Tuple[int, int]],
    ) -> List[InterlinearToken]:
        alignment_map = {}
        for source_index, translation_index in alignments:
            if source_index < len(source_tokens) and translation_index < len(translation_tokens):
                alignment_map[source_index] = translation_index

        aligned = []
        for index, source in enumerate(source_tokens):
            translation_index = alignment_map.get(index, -1)
            translation = translation_tokens[translation_index] if translation_index >= 0 else ""
            aligned.append(
                InterlinearToken(
                    source_l1=source,
                    transliteration_l2="",
                    translation_l3=translation,
                )
            )

        return aligned

    def validate_alignment(self, tokens: List[InterlinearToken]) -> List[str]:
        warnings = []

        empty_sources = sum(1 for token in tokens if not token.source_l1.strip())
        if empty_sources:
            warnings.append(f"{empty_sources} tokens have empty source text")

        empty_translations = sum(1 for token in tokens if not token.translation_l3.strip())
        if empty_translations:
            warnings.append(f"{empty_translations} tokens have empty translations")

        long_translations = [
            token for token in tokens if len(token.translation_l3.split()) > 3
        ]
        if long_translations:
            warnings.append(f"{len(long_translations)} tokens have unusually long translations")

        return warnings
