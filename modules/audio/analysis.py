"""Advanced audio analysis and speech-recognition primitives."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Protocol

from modules.audio.processor import AudioMetadata, AudioProcessor


@dataclass(frozen=True)
class TranscriptSegment:
    """Recognized speech segment with timing metadata."""

    start_seconds: float
    end_seconds: float
    text: str
    confidence: Optional[float] = None
    speaker: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        return max(0.0, self.end_seconds - self.start_seconds)


@dataclass(frozen=True)
class SilenceGap:
    """Detected silence or low-speech interval."""

    start_seconds: float
    end_seconds: float
    duration_seconds: float


@dataclass(frozen=True)
class ChapterCandidate:
    """Likely chapter boundary derived from transcript/silence cues."""

    start_seconds: float
    title: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class AudioAnalysisResult:
    """Combined audio metadata, transcript, and segmentation analysis."""

    metadata: AudioMetadata
    transcript_segments: List[TranscriptSegment]
    silence_gaps: List[SilenceGap]
    chapter_candidates: List[ChapterCandidate]
    speech_duration_seconds: float
    speech_ratio: float
    word_count: int


class SpeechRecognizer(Protocol):
    """Protocol for pluggable speech recognizers."""

    def transcribe(self, input_path: str) -> List[TranscriptSegment]:
        """Return transcript segments for an audio file."""


class StaticSpeechRecognizer:
    """Deterministic recognizer useful for tests and offline demos."""

    def __init__(self, segments: List[TranscriptSegment]):
        self.segments = segments

    def transcribe(self, input_path: str) -> List[TranscriptSegment]:
        return list(self.segments)


class AudioAnalyzer:
    """Runs speech-recognition-ready analysis over audio and transcript data."""

    def __init__(
        self,
        processor: Optional[AudioProcessor] = None,
        recognizer: Optional[SpeechRecognizer] = None,
        min_silence_seconds: float = 1.0,
        chapter_gap_seconds: float = 4.0,
    ):
        self.processor = processor or AudioProcessor()
        self.recognizer = recognizer
        self.min_silence_seconds = min_silence_seconds
        self.chapter_gap_seconds = chapter_gap_seconds

    def analyze(self, input_path: str, transcript_segments: Optional[List[TranscriptSegment]] = None) -> AudioAnalysisResult:
        """Analyze audio metadata and transcript timing."""
        metadata = self.processor.probe_metadata(input_path)
        segments = transcript_segments
        if segments is None:
            if not self.recognizer:
                segments = []
            else:
                segments = self.recognizer.transcribe(str(input_path))

        normalized_segments = self.normalize_segments(segments)
        silence_gaps = self.detect_silence_gaps(
            normalized_segments,
            total_duration_seconds=metadata.duration_seconds,
        )
        chapter_candidates = self.detect_chapter_candidates(normalized_segments, silence_gaps)
        speech_duration = sum(segment.duration_seconds for segment in normalized_segments)
        speech_ratio = speech_duration / metadata.duration_seconds if metadata.duration_seconds > 0 else 0.0
        word_count = sum(len(segment.text.split()) for segment in normalized_segments)

        return AudioAnalysisResult(
            metadata=metadata,
            transcript_segments=normalized_segments,
            silence_gaps=silence_gaps,
            chapter_candidates=chapter_candidates,
            speech_duration_seconds=speech_duration,
            speech_ratio=speech_ratio,
            word_count=word_count,
        )

    def normalize_segments(self, segments: List[TranscriptSegment]) -> List[TranscriptSegment]:
        """Sort and validate transcript segments."""
        normalized = sorted(segments, key=lambda segment: (segment.start_seconds, segment.end_seconds))
        for segment in normalized:
            if segment.start_seconds < 0:
                raise ValueError("Transcript segment start time cannot be negative")
            if segment.end_seconds < segment.start_seconds:
                raise ValueError("Transcript segment end time cannot precede start time")
        return normalized

    def detect_silence_gaps(
        self,
        segments: List[TranscriptSegment],
        total_duration_seconds: Optional[float] = None,
    ) -> List[SilenceGap]:
        """Infer silence gaps from transcript segment timing."""
        gaps: List[SilenceGap] = []
        previous_end = 0.0

        for segment in segments:
            if segment.start_seconds - previous_end >= self.min_silence_seconds:
                gaps.append(self._make_gap(previous_end, segment.start_seconds))
            previous_end = max(previous_end, segment.end_seconds)

        if total_duration_seconds is not None and total_duration_seconds - previous_end >= self.min_silence_seconds:
            gaps.append(self._make_gap(previous_end, total_duration_seconds))

        return gaps

    def detect_chapter_candidates(
        self,
        segments: List[TranscriptSegment],
        silence_gaps: List[SilenceGap],
    ) -> List[ChapterCandidate]:
        """Detect likely chapter starts from heading phrases and long pauses."""
        candidates: Dict[float, ChapterCandidate] = {}
        long_gap_starts = {
            round(gap.end_seconds, 3): gap
            for gap in silence_gaps
            if gap.duration_seconds >= self.chapter_gap_seconds
        }

        for index, segment in enumerate(segments):
            heading = self._heading_title(segment.text)
            key = round(segment.start_seconds, 3)
            if heading:
                candidates[key] = ChapterCandidate(
                    start_seconds=segment.start_seconds,
                    title=heading,
                    confidence=0.9,
                    reason="heading phrase",
                )
                continue

            gap = long_gap_starts.get(key)
            if gap and index > 0:
                candidates[key] = ChapterCandidate(
                    start_seconds=segment.start_seconds,
                    title=self._fallback_title(segment.text, index + 1),
                    confidence=min(0.85, 0.55 + gap.duration_seconds / 20),
                    reason=f"long silence gap ({gap.duration_seconds:.1f}s)",
                )

        if segments and 0.0 not in candidates:
            first = segments[0]
            candidates[0.0] = ChapterCandidate(
                start_seconds=first.start_seconds,
                title=self._fallback_title(first.text, 1),
                confidence=0.6,
                reason="start of audio",
            )

        return sorted(candidates.values(), key=lambda candidate: candidate.start_seconds)

    def _heading_title(self, text: str) -> Optional[str]:
        normalized = text.strip().strip(":").strip()
        lowered = normalized.lower()
        heading_prefixes = ("chapter ", "section ", "part ", "lesson ")
        if lowered.startswith(heading_prefixes):
            return normalized
        return None

    def _fallback_title(self, text: str, number: int) -> str:
        words = text.strip().split()
        if not words:
            return f"Chapter {number}"
        return " ".join(words[:6]).rstrip(".,:;") or f"Chapter {number}"

    def _make_gap(self, start: float, end: float) -> SilenceGap:
        return SilenceGap(
            start_seconds=start,
            end_seconds=end,
            duration_seconds=end - start,
        )
