import tempfile
from pathlib import Path
from recon_agent.tools.load_csv import LoadCSV, LoadCSVInput


def _write(path: Path, content: str, encoding: str = "utf-8") -> None:
    path.write_text(content, encoding=encoding)


def test_load_utf8_csv(tmp_path):
    p = tmp_path / "x.csv"
    _write(p, "a,b\n1,2\n3,4\n")
    result = LoadCSV().run(LoadCSVInput(path=str(p)))
    assert result.ok
    assert result.output.row_count == 2
    assert result.output.detected_encoding == "utf-8"
    assert result.output.rows[0] == {"a": "1", "b": "2"}


def test_load_latin1_csv(tmp_path):
    p = tmp_path / "x.csv"
    _write(p, "merchant,val\nMyntra,100\n", encoding="latin-1")
    result = LoadCSV().run(LoadCSVInput(path=str(p)))
    assert result.ok
    assert result.output.row_count == 1


def test_file_not_found(tmp_path):
    result = LoadCSV().run(LoadCSVInput(path=str(tmp_path / "missing.csv")))
    assert not result.ok
    assert result.error.code == "FILE_NOT_FOUND"
    assert result.error.kind == "fatal"
