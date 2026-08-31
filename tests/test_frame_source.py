"""
Tests de las fuentes de frames (FrameSource): video limpio + frame_mapping y stub en vivo.
"""
import json

import cv2
import numpy as np
import pytest

from app.core.ingestion.frame_source import FrameSample, LiveFrameSource, VideoFileFrameSource


@pytest.fixture()
def tiny_video(tmp_path):
    """Genera un mini video (20 frames, 64x48, 5 fps) para pruebas."""
    path = tmp_path / "tiny_clean.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 5.0, (64, 48))
    rng = np.random.default_rng(42)
    for _ in range(20):
        frame = (rng.random((48, 64, 3)) * 255).astype(np.uint8)
        writer.write(frame)
    writer.release()
    return path


def test_video_file_source_iterates_with_translated_timestamps(tiny_video, tmp_path):
    """Itera el video y traduce el timestamp con el frame_mapping del sidecar."""
    mapping = [
        {"clean_frame": 0, "original_frame": 0, "original_timestamp_sec": 0.0},
        {"clean_frame": 1, "original_frame": 3, "original_timestamp_sec": 0.6},
        {"clean_frame": 2, "original_frame": 5, "original_timestamp_sec": 1.0},
    ]
    sidecar = tiny_video.with_suffix(".json")
    sidecar.write_text(json.dumps({"frame_mapping": mapping}), encoding="utf-8")

    source = VideoFileFrameSource(tiny_video)
    try:
        assert source.fps == 5.0

        first = source.next_frame()
        assert isinstance(first, FrameSample)
        assert first.frame_index == 0
        assert first.timestamp_sec == 0.0
        assert first.frame.shape == (48, 64, 3)

        second = source.next_frame()
        assert second.frame_index == 1
        assert second.timestamp_sec == 0.6  # traducido vía mapping, no frame_index/fps

        third = source.next_frame()
        assert third.timestamp_sec == 1.0
    finally:
        source.close()


def test_video_file_source_fallback_to_fps(tiny_video):
    """Sin sidecar ni mapping, el timestamp cae al fallback frame_index/fps."""
    source = VideoFileFrameSource(tiny_video, frame_mapping=[], fps=5.0)
    try:
        sample = source.next_frame()
        assert sample.timestamp_sec == 0.0  # frame 0 / 5.0
        sample = source.next_frame()
        assert sample.timestamp_sec == 0.2  # frame 1 / 5.0
    finally:
        source.close()


def test_missing_video_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        VideoFileFrameSource(tmp_path / "no_existe.mp4")


def test_live_source_is_stub():
    """LiveFrameSource es un stub pendiente de Team 1 (lanzar NotImplementedError)."""
    source = LiveFrameSource(source_id="webcam_0")
    assert source.fps > 0
    with pytest.raises(NotImplementedError):
        source.next_frame()
    source.close()  # no debe explotar