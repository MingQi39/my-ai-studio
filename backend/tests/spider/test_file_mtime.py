from app.spider.services.file_mtime import format_file_mtime, parse_ls_line


def test_format_file_mtime_converts_utc_epoch_to_shanghai():
    # 2026-07-14 03:27:00 UTC → 11:27 Asia/Shanghai
    epoch = 1_783_999_620
    assert format_file_mtime(epoch) == "Jul 14 11:27"


def test_parse_ls_line_with_epoch_time_style():
    line = "-rw-r--r-- 1 root root 3991 1784007340 spider.py"
    entry = parse_ls_line(line)
    assert entry == {
        "permissions": "-rw-r--r--",
        "links": "1",
        "owner": "root",
        "group": "root",
        "size": "3991",
        "mtime": 1784007340,
        "name": "spider.py",
    }


def test_parse_ls_line_skips_total_and_short_lines():
    assert parse_ls_line("total 148") is None
    assert parse_ls_line("") is None
