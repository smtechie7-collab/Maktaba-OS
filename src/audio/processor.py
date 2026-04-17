import os
import sys
from pydub import AudioSegment
from pydub.utils import mediainfo
from typing import List, Optional

# Add root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.utils.logger import setup_logger

logger = setup_logger("AudioProcessor")

class AudioProcessor:
    def __init__(self, target_lufs: float = -16.0):
        self.target_lufs = target_lufs

    def normalize_audio(self, audio: AudioSegment) -> AudioSegment:
        """Normalize audio to the target LUFS (approximate using dBFS)."""
        change_in_dbfs = self.target_lufs - audio.dBFS
        return audio.apply_gain(change_in_dbfs)

    def process_chapters(self, input_files: List[str], output_path: str, crossfade_ms: int = 1000):
        """
        Merge multiple audio files with normalization and crossfades.
        
        Args:
            input_files: List of paths to audio files (mp3, wav, etc.)
            output_path: Path to save the final merged file.
            crossfade_ms: Duration of crossfade between files in milliseconds.
        """
        if not input_files:
            logger.error("No input files provided for audio processing.")
            return

        logger.info(f"Processing {len(input_files)} audio files...")
        
        combined_audio = None

        for file_path in input_files:
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}. Skipping.")
                continue

            logger.info(f"Loading and normalizing: {file_path}")
            current_audio = AudioSegment.from_file(file_path)
            current_audio = self.normalize_audio(current_audio)

            if combined_audio is None:
                combined_audio = current_audio
            else:
                # Append with crossfade
                combined_audio = combined_audio.append(current_audio, crossfade=crossfade_ms)

        if combined_audio:
            logger.info(f"Exporting merged audio to: {output_path}")
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            combined_audio.export(output_path, format="mp3", bitrate="192k")
            logger.info("Audio processing complete.")
        else:
            logger.error("Failed to produce combined audio.")

if __name__ == "__main__":
    # Example usage (Test block)
    # Note: This requires sample mp3 files to actually run.
    processor = AudioProcessor()
    
    # Placeholder for test
    logger.info("AudioProcessor initialized. To test, provide actual mp3 paths.")
    
    # In a real scenario, we would fetch paths from the database
    # sample_files = ["assets/audio/chapter1.mp3", "assets/audio/chapter2.mp3"]
    # processor.process_chapters(sample_files, "output/final_book_audio.mp3")
