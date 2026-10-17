"""Measured output clocks independent of cache lookup and publication."""
from fractions import Fraction

from .render_contracts import RenderContractError, quantize, ratio, rational
from .subtitles import segment_output_duration


def time_entry(segment_id: str, start: Fraction, duration: Fraction, fps: Fraction) -> dict:
    end = start + duration
    sf, ef = quantize(start * fps), quantize(end * fps)
    ss, es = quantize(start * 48000), quantize(end * 48000)
    return {"segment_id": segment_id, "start": ratio(start), "end": ratio(end),
            "duration": ratio(duration), "start_frame": sf, "end_frame": ef,
            "start_sample": ss, "end_sample": es,
            "frame_rounding_residual": ratio(end * fps - ef),
            "sample_rounding_residual": ratio(end * 48000 - es)}



def realized_duration(segment, contract, fps, duration):
    sid = segment.segment_id
    frames = contract.get("frame_count")
    if isinstance(frames, bool) or not isinstance(frames, int) or frames <= 0:
        raise RenderContractError(f"REALIZED_FRAME_COUNT_MISSING: {sid}")
    samples = contract.get("sample_count")
    if isinstance(samples, bool) or not isinstance(samples, int) or samples <= 0:
        raise RenderContractError(f"REALIZED_SAMPLE_COUNT_MISSING: {sid}")
    if rational(contract.get("fps", 0)) != fps:
        raise RenderContractError(f"REALIZED_FPS_MISMATCH: {sid}")
    actual = Fraction(frames, 1) / fps
    if contract.get("sample_rate") != 48000:
        raise RenderContractError(f"REALIZED_SAMPLE_RATE_MISMATCH: {sid}")
    decoded = contract.get("decoded_sample_count")
    padding = contract.get("padding")
    delay = contract.get("encoder_delay")
    if (any(type(v) is not int or v < 0 for v in (decoded, padding, delay))
            or decoded != samples + padding or padding > 8192 or delay > 8192
            or contract.get("padding_policy") != "decoded-minus-packet-end/1"):
        raise RenderContractError(f"REALIZED_AUDIO_PADDING_INVALID: {sid}")
    if abs(Fraction(samples, 48000) - actual) > 1 / fps:
        raise RenderContractError(f"REALIZED_AUDIO_VIDEO_DRIFT: {sid}")
    for boundary in segment.tts_word_boundaries if segment.mode == "voiceover" else []:
        start = rational(boundary.get("start", 0))
        end = start + rational(boundary.get("duration", 0))
        if start < 0 or end > Fraction(samples + 1, 48000) or start >= Fraction(samples, 48000):
            raise RenderContractError(f"WORD_OUTSIDE_REALIZED_AUDIO: {sid}")
    if abs(actual - duration) > 1 / fps:
        raise RenderContractError(f"REALIZED_DURATION_DRIFT: {sid}")
    return actual


def build_realized_timeline(storyboard, fps_value, contracts):
    fps = rational(fps_value)
    cursor = expected_cursor = Fraction(0)
    timeline = []
    for segment in storyboard.segments:
        expected = rational(segment_output_duration(segment))
        actual = realized_duration(segment, contracts[segment.segment_id], fps, expected)
        timeline.append(time_entry(segment.segment_id, cursor, actual, fps))
        cursor += actual
        expected_cursor += expected
        if abs(cursor - expected_cursor) > 1 / fps:
            raise RenderContractError(f"REALIZED_CUMULATIVE_DRIFT: {segment.segment_id}")
    return timeline
