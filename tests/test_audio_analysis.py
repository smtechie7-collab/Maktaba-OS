"""
Tests for advanced audio analysis primitives.
"""

import pytest

from modules.audio import (
    AudioAnalyzer,
    AudioMetadata,
    StaticSpeechRecognizer,
    TranscriptSegment,
)


class FakeAudioProcessor:
    """AudioProcessor test double returning fixed metadata."""

    def __init__(self, duration_seconds=30.0):
        self.metadata = AudioMetadata(
            duration_seconds=duration_seconds,
            sample_rate=44100,
            channels=1,
            codec_name="pcm_s16le",
            bit_rate=705600,
        )

    def probe_metadata(self, input_path):
        return self.metadata


def test_analyze_audio_with_static_recognizer():
    """Analyzer should combine metadata, transcript, gaps, and summary stats."""
    segments = [
        TranscriptSegment(0.0, 2.0, "Chapter One"),
        TranscriptSegment(3.0, 5.0, "In the beginning"),
        TranscriptSegment(10.0, 12.0, "Chapter Two"),
    ]
    analyzer = AudioAnalyzer(
        processor=FakeAudioProcessor(duration_seconds=15),
        recognizer=StaticSpeechRecognizer(segments),
        min_silence_seconds=1.0,
        chapter_gap_seconds=4.0,
    )

    result = analyzer.analyze("sample.wav")

    assert result.metadata.duration_seconds == 15
    assert result.speech_duration_seconds == 6
    assert result.speech_ratio == pytest.approx(0.4)
    assert result.word_count == 7
    assert [(gap.start_seconds, gap.end_seconds) for gap in result.silence_gaps] == [
        (2.0, 3.0),
        (5.0, 10.0),
        (12.0, 15),
    ]
    assert [candidate.title for candidate in result.chapter_candidates] == [
        "Chapter One",
        "Chapter Two",
    ]


def test_detect_chapter_candidate_from_long_silence():
    """Long gaps should produce chapter candidates even without explicit headings."""
    analyzer = AudioAnalyzer(
        processor=FakeAudioProcessor(duration_seconds=20),
        min_silence_seconds=1.0,
        chapter_gap_seconds=4.0,
    )
    segments = [
        TranscriptSegment(0.0, 2.0, "Opening remarks and context"),
        TranscriptSegment(8.0, 10.0, "New theme begins here with evidence"),
    ]

    result = analyzer.analyze("sample.wav", transcript_segments=segments)

    assert [candidate.reason for candidate in result.chapter_candidates] == [
        "start of audio",
        "long silence gap (6.0s)",
    ]
    assert result.chapter_candidates[1].title == "New theme begins here with evidence"
    assert result.chapter_candidates[1].confidence > 0.8


def test_analyzer_without_recognizer_still_reports_metadata():
    """Analyzer should work without speech recognition and return empty transcript data."""
    analyzer = AudioAnalyzer(processor=FakeAudioProcessor(duration_seconds=9))

    result = analyzer.analyze("sample.wav")

    assert result.transcript_segments == []
    assert result.speech_duration_seconds == 0
    assert result.speech_ratio == 0
    assert result.word_count == 0
    assert result.silence_gaps == [
        analyzer._make_gap(0.0, 9)
    ]


def test_segment_validation_rejects_negative_start():
    """Transcript timing must be sane before analysis proceeds."""
    analyzer = AudioAnalyzer(processor=FakeAudioProcessor())

    with pytest.raises(ValueError, match="start time"):
        analyzer.analyze(
            "sample.wav",
            transcript_segments=[TranscriptSegment(-1.0, 2.0, "bad")],
        )


def test_segment_validation_rejects_reversed_times():
    """Transcript segment end cannot precede start."""
    analyzer = AudioAnalyzer(processor=FakeAudioProcessor())

    with pytest.raises(ValueError, match="end time"):
        analyzer.analyze(
            "sample.wav",
            transcript_segments=[TranscriptSegment(5.0, 3.0, "bad")],
        )
