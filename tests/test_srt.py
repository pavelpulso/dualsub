from pathlib import Path

from dualsub.srt import Cue, format_srt, format_timestamp, parse_srt, parse_timestamp
from dualsub.dual import merge_dual

SAMPLE = Path(__file__).parent.parent / "examples" / "sample.es.srt"


def test_timestamp_roundtrip():
    assert format_timestamp(3661.5) == "01:01:01,500"
    assert abs(parse_timestamp("01:01:01,500") - 3661.5) < 1e-6


def test_parse_sample():
    cues = parse_srt(SAMPLE)
    assert len(cues) == 2
    assert cues[0].text == "No hay nada que contar"
    assert cues[0].start == 1.0
    assert cues[1].end == 5.2


def test_format_parse_roundtrip(tmp_path):
    cues = parse_srt(SAMPLE)
    out = tmp_path / "out.srt"
    out.write_text(format_srt(cues), encoding="utf-8")
    again = parse_srt(out)
    assert [c.text for c in again] == [c.text for c in cues]
    assert [c.start for c in again] == [c.start for c in cues]


def test_dual_merge_equal_length():
    top = [Cue(1, 1.0, 3.0, "hola"), Cue(2, 3.5, 5.0, "adios")]
    bottom = [Cue(1, 1.0, 3.0, "hi"), Cue(2, 3.5, 5.0, "bye")]
    merged = merge_dual(top, bottom)
    assert merged[0].text == "hola\nhi"
    assert merged[1].text == "adios\nbye"
    assert merged[0].start == 1.0


def test_dual_merge_mismatched_uses_nearest():
    top = [Cue(1, 1.0, 3.0, "hola")]
    bottom = [Cue(1, 10.0, 11.0, "far"), Cue(2, 1.1, 2.0, "near")]
    merged = merge_dual(top, bottom)
    assert merged[0].text == "hola\nnear"
