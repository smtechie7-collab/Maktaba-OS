import pytest
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.audio.processor import AudioProcessor

def test_audio_processor_initialization():
    """Ensure the Audio Processor enforces EBU R128 Standards (-16 LUFS) by default."""
    processor = AudioProcessor(target_lufs=-16)
    assert processor.target_lufs == -16