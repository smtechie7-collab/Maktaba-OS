import json
import subprocess

from modules.audio import AudioProcessor


def test_audio_processor_initialization():
    """Ensure the audio processor defaults to EBU R128 speech normalization."""
    processor = AudioProcessor(target_lufs=-16)
    assert processor.target_lufs == -16


def test_audio_tool_availability_uses_path_lookup(monkeypatch):
    processor = AudioProcessor()

    monkeypatch.setattr("modules.audio.processor.shutil.which", lambda tool: f"/bin/{tool}")

    assert processor.has_ffmpeg() is True
    assert processor.has_ffprobe() is True


def test_build_normalization_args():
    processor = AudioProcessor(target_lufs=-16, true_peak=-1.5, loudness_range=11)

    command = processor.build_normalization_args("input.wav", "output.wav")

    assert command == [
        "ffmpeg",
        "-y",
        "-i",
        "input.wav",
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11",
        "output.wav",
    ]


def test_probe_metadata_parses_ffprobe_json(tmp_path, monkeypatch):
    audio_file = tmp_path / "sample.wav"
    audio_file.write_bytes(b"fake audio")
    payload = {
        "streams": [
            {
                "codec_type": "audio",
                "codec_name": "pcm_s16le",
                "sample_rate": "44100",
                "channels": 2,
            }
        ],
        "format": {
            "duration": "12.5",
            "bit_rate": "1411200",
        },
    }

    def fake_run(command, capture_output, text, check):
        assert command[0] == "ffprobe"
        assert str(audio_file) in command
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload))

    monkeypatch.setattr("modules.audio.processor.subprocess.run", fake_run)

    metadata = AudioProcessor().probe_metadata(audio_file)

    assert metadata.duration_seconds == 12.5
    assert metadata.sample_rate == 44100
    assert metadata.channels == 2
    assert metadata.codec_name == "pcm_s16le"
    assert metadata.bit_rate == 1411200


def test_probe_metadata_rejects_missing_file(tmp_path):
    missing_file = tmp_path / "missing.wav"

    try:
        AudioProcessor().probe_metadata(missing_file)
    except FileNotFoundError as exc:
        assert "missing.wav" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError")


def test_normalize_audio_runs_ffmpeg_command(tmp_path, monkeypatch):
    input_file = tmp_path / "input.wav"
    output_file = tmp_path / "nested" / "output.wav"
    input_file.write_bytes(b"fake audio")
    calls = []

    monkeypatch.setattr("modules.audio.processor.shutil.which", lambda tool: f"/bin/{tool}")

    def fake_run(command, capture_output, text, check):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="")

    monkeypatch.setattr("modules.audio.processor.subprocess.run", fake_run)

    result = AudioProcessor().normalize_audio(input_file, output_file)

    assert result == output_file
    assert output_file.parent.exists()
    assert calls == [AudioProcessor().build_normalization_args(input_file, output_file)]


def test_normalize_audio_requires_ffmpeg(tmp_path, monkeypatch):
    input_file = tmp_path / "input.wav"
    output_file = tmp_path / "output.wav"
    input_file.write_bytes(b"fake audio")
    monkeypatch.setattr("modules.audio.processor.shutil.which", lambda tool: None)

    try:
        AudioProcessor().normalize_audio(input_file, output_file)
    except RuntimeError as exc:
        assert "ffmpeg" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")
