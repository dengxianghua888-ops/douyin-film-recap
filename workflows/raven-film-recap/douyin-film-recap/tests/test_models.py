from __future__ import annotations

import pytest
from pydantic import ValidationError

from douyin_film_recap.models import TimeSpan, TranscriptWord


def test_time_span_rejects_reverse_range() -> None:
    with pytest.raises(ValidationError):
        TimeSpan(source_id="src_001", start=2.0, end=1.0)


def test_transcript_word_accepts_valid_range() -> None:
    word = TranscriptWord(start=1.0, end=1.4, text="你好")
    assert word.end - word.start == pytest.approx(0.4)
