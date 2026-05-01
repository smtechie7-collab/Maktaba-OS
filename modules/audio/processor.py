"""Audio processing primitives for Maktaba-OS."""

from dataclasses import dataclass
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Union


@dataclass(frozen=True)
class AudioMetadata:
    """Basic audio metadata returned by ffprobe."""

    duration_seconds: float
    sample_rate: Optional[int]
    channels: Optional[int]
    codec_name: Optional[str]
    bit_rate: Optional[int]


class AudioProcessor:
    """Coordinates FFmpeg-backed audio checks and command construction."""

    def __init__(self, target_lufs: int = -16, true_peak: float = -1.5, loudness_range: int = 11):
        self.target_lufs = target_lufs
        self.true_peak = true_peak
        self.loudness_range = loudness_range

    def has_ffmpeg(self) -> bool:
        return self._tool_available("ffmpeg")

    def has_ffprobe(self) -> bool:
        return self._tool_available("ffprobe")

    def probe_metadata(self, input_path: Union[str, Path]) -> AudioMetadata:
        """Read audio metadata using ffprobe JSON output."""
        path = Path(input_path)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")

        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
        )
        payload = json.loads(completed.stdout)
        streams = payload.get("streams", [])
        audio_stream = next(
            (stream for stream in streams if stream.get("codec_type") == "audio"),
            streams[0] if streams else {},
        )
        format_data = payload.get("format", {})

        duration = float(format_data.get("duration") or audio_stream.get("duration") or 0)
        sample_rate = self._optional_int(audio_stream.get("sample_rate"))
        channels = self._optional_int(audio_stream.get("channels"))
        bit_rate = self._optional_int(format_data.get("bit_rate") or audio_stream.get("bit_rate"))

        return AudioMetadata(
            duration_seconds=duration,
            sample_rate=sample_rate,
            channels=channels,
            codec_name=audio_stream.get("codec_name"),
            bit_rate=bit_rate,
        )

    def build_normalization_args(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> List[str]:
        """Build an FFmpeg command for EBU R128 loudness normalization."""
        loudnorm = (
            f"loudnorm=I={self.target_lufs}:"
            f"TP={self.true_peak}:"
            f"LRA={self.loudness_range}"
        )
        return [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-af",
            loudnorm,
            str(output_path),
        ]

    def normalize_audio(self, input_path: Union[str, Path], output_path: Union[str, Path]) -> Path:
        """Normalize audio loudness with FFmpeg and return the output path."""
        source = Path(input_path)
        target = Path(output_path)
        if not source.exists():
            raise FileNotFoundError(f"Audio file not found: {source}")
        if not self.has_ffmpeg():
            raise RuntimeError("ffmpeg is required for audio normalization")

        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            self.build_normalization_args(source, target),
            capture_output=True,
            text=True,
            check=True,
        )
        return target

    def _tool_available(self, tool_name: str) -> bool:
        return shutil.which(tool_name) is not None

    @staticmethod
    def _optional_int(value) -> Optional[int]:
        if value in (None, ""):
            return None
        return int(value)
