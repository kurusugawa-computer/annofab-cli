from __future__ import annotations

import pytest

from annofabcli.__main__ import main


def test_bash用の補完スクリプトを出力する(capsys: pytest.CaptureFixture[str]) -> None:
    main(["completion", "bash"])

    captured = capsys.readouterr()
    assert "complete -F _shtab_annofabcli annofabcli" in captured.out
    assert "--project_id" in captured.out
