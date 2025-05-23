from annofabcli.__main__ import mask_sensitive_value_in_argv


def test__mask_sensitive_value_in_argv__password():
    actual = mask_sensitive_value_in_argv(["--annofab_user_id", "alice", "--annofab_password", "pw"])
    assert actual == ["--annofab_user_id", "***", "--annofab_password", "***"]


def test__mask_sensitive_value_in_argv__同じ引数を指定する():
    actual = mask_sensitive_value_in_argv(["--annofab_user_id", "alice", "--annofab_password", "pw_alice", "--annofab_user_id", "bob", "--annofab_password", "pw_bob"])
    assert actual == ["--annofab_user_id", "***", "--annofab_password", "***", "--annofab_user_id", "***", "--annofab_password", "***"]


def test__mask_sensitive_value_in_argv__pat():
    actual = mask_sensitive_value_in_argv(["--annofab_pat", "token"])
    assert actual == ["--annofab_pat", "***"]
