from pathlib import Path

from tools.generate_eval_audio_elevenlabs import write_wav_from_pcm_s16le


def test_write_wav_from_pcm_s16le_writes_valid_wav(tmp_path: Path):
    # 100 samples of silence at 16kHz, 16-bit little endian
    pcm = b"\x00\x00" * 100
    out = tmp_path / "out.wav"
    write_wav_from_pcm_s16le(pcm, out, sample_rate=16000)

    assert out.exists()
    assert out.stat().st_size > 44  # WAV header is 44 bytes
