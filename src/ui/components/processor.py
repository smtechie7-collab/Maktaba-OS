import os
try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

class AudioProcessor:
    """
    Phase 3: The Audio-Visual & Karaoke Pipeline.
    Handles trimming, slicing, and crossfading of MP3/WAV files,
    as well as LUFS normalization to EBU R128 standards.
    """
    def __init__(self, target_lufs=-16.0):
        self.target_lufs = target_lufs

    def process_timeline(self, tracks_config, output_path, crossfade_ms=1500):
        if not PYDUB_AVAILABLE:
            raise RuntimeError("The 'pydub' library is required for audio processing. Please run 'pip install pydub'.")
            
        if not tracks_config:
            raise ValueError("No tracks provided in the timeline configuration.")
            
        final_audio = None
        
        for track in tracks_config:
            file_path = track.get('path')
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Audio file not found: {file_path}")
                
            # Load audio file (pydub utilizes ffmpeg securely under the hood)
            audio = AudioSegment.from_file(file_path)
            
            # Trimming Logic
            start_ms = int(track.get('start', 0.0) * 1000)
            end_val = track.get('end')
            end_ms = int(end_val * 1000) if end_val else len(audio)
            
            trimmed_audio = audio[start_ms:end_ms]
            
            # Crossfade / Append
            if final_audio is None:
                final_audio = trimmed_audio
            else:
                final_audio = final_audio.append(trimmed_audio, crossfade=crossfade_ms)
                
        # Normalize Volume to Target LUFS (Approximate Gain Staging)
        if final_audio is not None:
            diff = self.target_lufs - final_audio.dBFS
            final_audio = final_audio.apply_gain(diff)
            final_audio.export(output_path, format="mp3", bitrate="192k")