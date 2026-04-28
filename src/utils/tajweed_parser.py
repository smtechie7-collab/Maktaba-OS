import re
from typing import List, Tuple

class TajweedEngine:
    """
    A pure Regex/NLP parser for identifying Tajweed rules in Arabic text.
    Operates purely on the memory/UI layer to preserve the Sacredness of Data.
    """
    # Arabic Unicode Constants
    SUKOON = "\u0652"
    SHADDA = "\u0651"
    FATHATAN = "\u064B"
    KASRATAN = "\u064D"
    DAMMATAN = "\u064C"
    MADDAH = "\u0653"
    ALEF_MADDAH = "\u0622"
    NOON = "ن"
    MEEM = "م"
    
    TANWEEN = f"[{FATHATAN}{KASRATAN}{DAMMATAN}]"

    # --- RULE SETS ---
    # 1. Qalqalah: ق ط ب ج د with Sukoon
    QALQALAH_LETTERS = "[قطبجد]"
    # 2. Ghunnah: Noon or Meem with Shadda
    GHUNNAH_LETTERS = f"[{NOON}{MEEM}]"
    # 3. Ikhfaa: Noon Saakin or Tanween followed by 15 specific letters
    IKHFAA_LETTERS = "[تثجدذزسشصضطظفقك]"
    # 4. Idghaam: Noon Saakin or Tanween followed by ي ن م و ر ل
    IDGHAAM_LETTERS = "[ينمورل]"

    RULES = [
        # (Rule Name, Compiled Regex Pattern, PyQt Hex Color, Print CSS Class)
        ("qalqalah", re.compile(f"({QALQALAH_LETTERS}{SUKOON})"), "#DC2626", "t-qalqalah"), # Red
        ("ghunnah", re.compile(f"({GHUNNAH_LETTERS}{SHADDA})"), "#D97706", "t-ghunnah"), # Orange/Gold
        # Using Lookahead (?=...) prevents coloring the spaces between words for cleaner typography
        ("ikhfaa", re.compile(f"({NOON}{SUKOON}|{TANWEEN})(?=\s*{IKHFAA_LETTERS})"), "#2563EB", "t-ikhfaa"), # Blue
        ("idghaam", re.compile(f"({NOON}{SUKOON}|{TANWEEN})(?=\s*{IDGHAAM_LETTERS})"), "#16A34A", "t-idghaam"), # Green
        ("madd", re.compile(f"({ALEF_MADDAH}|[\u0621-\u064A][\u064B-\u065F]*{MADDAH})"), "#9333EA", "t-madd"), # Purple
    ]

    @classmethod
    def get_tajweed_ranges(cls, text: str) -> List[Tuple[int, int, str]]:
        """
        Returns a list of (start_index, length, hex_color) for PyQt UI highlighting.
        """
        ranges = []
        if not text: return ranges

        for name, pattern, color, css_class in cls.RULES:
            for match in pattern.finditer(text):
                start = match.start()
                length = match.end() - start
                ranges.append((start, length, color))
        
        return ranges

    @classmethod
    def apply_html(cls, text: str) -> str:
        """
        Wraps matched Tajweed rules in HTML spans with inline colors for PDF/WebEngine.
        """
        if not text: return text
        
        for name, pattern, color, css_class in cls.RULES:
            # Replace exactly what matched with a wrapped span, preserving existing characters
            text = pattern.sub(lambda m: f'<span class="{css_class}" style="color: {color};">{m.group(0)}</span>', text)
            
        return text