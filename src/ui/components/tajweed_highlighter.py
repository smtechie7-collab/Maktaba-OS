from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor
from PyQt6.QtCore import Qt
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from src.utils.tajweed_parser import TajweedEngine

class TajweedHighlighter(QSyntaxHighlighter):
    """Dynamically applies Tajweed colors to an active text editor without modifying the text."""
    
    def __init__(self, document):
        super().__init__(document)
        self.is_enabled = False

    def set_enabled(self, enabled: bool):
        self.is_enabled = enabled
        self.rehighlight()

    def highlightBlock(self, text: str):
        if not self.is_enabled or not text:
            return

        ranges = TajweedEngine.get_tajweed_ranges(text)
        for start, length, color_hex in ranges:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color_hex))
            self.setFormat(start, length, fmt)