import datetime
import os
import sys


# Ensure src/ is importable when tests run from project root
HERE = os.path.dirname(__file__)
SRC = os.path.abspath(os.path.join(HERE, "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from cli import parse_args, to_unix  # noqa: E402


def test_parse_args_minimal_update():
    args = parse_args(["--section-id", "1", "--type", "movie", "--date", "2024-01-15"])
    assert args.section_id == "1"
    assert args.type == "movie"
    assert args.date == "2024-01-15"


def test_parse_args_list_sections():
    args = parse_args(["--list-sections"])  # no validation of update flags in this mode
    assert args.list_sections is True


def test_to_unix_valid_roundtrip():
    ds = "2024-01-15"
    expected = int(datetime.datetime.combine(datetime.date(2024, 1, 15), datetime.time.min).timestamp())
    assert to_unix(ds) == expected


def test_to_unix_invalid_raises():
    try:
        to_unix("2024-13-40")
        assert False, "Expected SystemExit for invalid date"
    except SystemExit as e:
        assert "Invalid --date value" in str(e)

