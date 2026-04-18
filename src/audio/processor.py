import os
import sys
import json
from pydub import AudioSegment
from typing import List, Dict, Optional

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
        """Legacy sequential merge (kept for backward compatibility)."""
        if not input_files:
            logger.error("No input files provided.")
            return

        logger.info(f"Legacy Mode: Processing {len(input_files)} audio files...")
        combined_audio = None

        for file_path in input_files:
            if not os.path.exists(file_path):
                logger.warning(f"File not found: {file_path}. Skipping.")
                continue

            current_audio = AudioSegment.from_file(file_path)
            
            if combined_audio is None:
                combined_audio = current_audio
            else:
                combined_audio = combined_audio.append(current_audio, crossfade=crossfade_ms)

        if combined_audio:
            combined_audio = self.normalize_audio(combined_audio)
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            combined_audio.export(output_path, format="mp3", bitrate="192k")
            logger.info("Legacy audio processing complete.")

    def build_from_recipe(self, recipe: Dict, source_dir: str, output_dir: str) -> None:
        """
        PILLAR 4: Node-Based Audio Routing.
        Builds multiple audio files based on a JSON recipe. Engine is now agnostic.
        """
        logger.info("Starting Config-Driven Audio Routing...")
        os.makedirs(output_dir, exist_ok=True)

        for playlist_name, config in recipe.items():
            logger.info(f"Building track sequence for: {playlist_name}")
            track_names = config.get("tracks", [])
            crossfade_ms = config.get("crossfade", 1500)
            
            combined_audio = None
            
            for track_name in track_names:
                file_path = os.path.join(source_dir, track_name)
                if not os.path.exists(file_path):
                    logger.warning(f"Missing source track '{track_name}' for '{playlist_name}'. Engine will skip this segment.")
                    continue
                    
                logger.info(f"  -> Loading node: {track_name}")
                current_audio = AudioSegment.from_file(file_path)
                
                if combined_audio is None:
                    combined_audio = current_audio
                else:
                    combined_audio = combined_audio.append(current_audio, crossfade=crossfade_ms)
            
            if combined_audio:
                # Apply Master LUFS Normalization to the final merged timeline
                logger.info(f"Normalizing '{playlist_name}' master track to {self.target_lufs} LUFS...")
                combined_audio = self.normalize_audio(combined_audio)
                
                out_path = os.path.join(output_dir, f"{playlist_name}.mp3")
                logger.info(f"Exporting Final Mix to: {out_path}")
                combined_audio.export(out_path, format="mp3", bitrate="192k")
                logger.info(f"✅ Successfully completed {playlist_name}\n")

if __name__ == "__main__":
    processor = AudioProcessor()
    logger.info("Maktaba-OS Audio Routing Engine initialized.")
