from dualsub.srt import Cue
from dualsub.tokenize import is_rare, rarity, words
from dualsub.vocab import collect_words
from dualsub.ass import write_ass


def test_tokenize_words():
    assert words("¡Hola, mundo! Está bien.") == ["hola", "mundo", "está", "bien"]


def test_rarity_common_vs_rare():
    assert rarity("casa", "es") > rarity("bisoñé", "es")
    assert rarity("the", "es") == 0 or rarity("xyzqwk", "es") == 0


def test_is_rare_threshold():
    assert not is_rare("casa", "es", max_zipf=4.0)   # common
    assert is_rare("bisoñé", "es", max_zipf=4.0)      # rare


def test_collect_words_filters_and_ranks():
    cues = [
        Cue(1, 0, 1, "La casa es grande"),
        Cue(2, 1, 2, "Tiene bisoñé y joroba"),
    ]
    got = collect_words(cues, "es", max_zipf=4.0, min_len=3)
    ws = [w for w, _, _ in got]
    assert "bisoñé" in ws
    assert "casa" not in ws                            # too common
    zipfs = [z for _, _, z in got]
    assert zipfs == sorted(zipfs)                      # rarest first


def test_ass_highlights_rare(tmp_path):
    cues = [Cue(1, 0, 2, "la casa tiene bisoñé")]
    out = write_ass(cues, tmp_path / "x.ass", lang="es", max_zipf=4.0)
    text = out.read_text(encoding="utf-8")
    assert "{\\c&H00D7FF&}bisoñé{\\r}" in text
    assert "{\\c&H00D7FF&}casa" not in text            # common word not colored
