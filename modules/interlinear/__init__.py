"""
Interlinear Rendering System for Maktaba-OS.
Provides interactive word-by-word translation and linguistic analysis display.
"""

from .interlinear_widget import InterlinearWidget
from .token_alignment import TokenAligner

__all__ = ['InterlinearWidget', 'TokenAligner']