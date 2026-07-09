from dualsub.progress import comprehension, load, record, summary


def test_comprehension_math():
    assert comprehension(90, 10) == 0.9
    assert comprehension(0, 0) is None
    assert comprehension(50, 0) == 1.0


def test_record_and_load(tmp_path):
    p = tmp_path / "progress.csv"
    record("ep1", 90, 10, path=p, today="2026-07-09")
    record("ep2", 60, 40, path=p, today="2026-07-09")
    rows = load(p)
    assert len(rows) == 2
    assert rows[0]["episode"] == "ep1"
    assert float(rows[0]["comprehension"]) == 0.9


def test_summary(tmp_path):
    p = tmp_path / "progress.csv"
    record("ep1", 90, 10, path=p)
    record("ep2", 70, 30, path=p)
    s = summary(load(p))
    assert s["episodes"] == 2
    assert s["avg_comprehension"] == 0.8
    assert s["last_comprehension"] == 0.7
