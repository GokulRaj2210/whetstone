import json

import pytest
from config import ConfigError, load_config
from startup import main


def test_malformed_config_raises(tmp_path):
    bad = tmp_path / "c.json"
    bad.write_text("{not json")
    with pytest.raises(ConfigError):
        load_config(str(bad))


def test_missing_config_raises(tmp_path):
    with pytest.raises(ConfigError):
        load_config(str(tmp_path / "nope.json"))


def test_good_config_still_loads(tmp_path):
    good = tmp_path / "c.json"
    good.write_text(json.dumps({"a": 1}))
    assert load_config(str(good)) == {"a": 1}


def test_startup_reports_the_failure(tmp_path, capsys):
    bad = tmp_path / "c.json"
    bad.write_text("{not json")
    assert main(str(bad)) == 1
