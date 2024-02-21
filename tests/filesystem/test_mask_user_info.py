from pathlib import Path

import pandas

from annofabcli.common.utils import read_multiheader_csv
from annofabcli.filesystem.mask_user_info import create_masked_name, create_masked_user_info_df

data_dir = Path("./tests/data/filesystem")


class TestMaskUserInfo:
    def test_create_masked_name(self):
        assert create_masked_name("abc") == "P"

    def test_create_masked_user_info_df__オプショナル引数を指定しない(self):
        # ヘッダ２行のCSVを読み込む
        df_original = read_multiheader_csv(str(data_dir / "user2.csv"), header_row_count=2)
        df_masked = create_masked_user_info_df(df_original)
        expected_masked_user_info = ["FF", "AA", "IK"]
        assert list(df_masked["user_id"]) == expected_masked_user_info
        assert list(df_masked["username"]) == expected_masked_user_info
        assert list(df_masked["account_id"]) == expected_masked_user_info
        assert list(df_masked["biography"]) == ["category-TD", "category-TD", "category-TU"]

        # ユーザー情報以外は変わっていないことの確認
        assert df_masked["task_count"].equals(df_original["task_count"])

    def test_create_masked_user_info_df__not_masked_biography_set引数を指定する(self):
        df_original = read_multiheader_csv(str(data_dir / "user2.csv"), header_row_count=2)
        df_masked = create_masked_user_info_df(
            df_original,
            not_masked_biography_set={"China"},
        )

        # biographyが"China"の行はマスクされていないこと、それ以外はマスクされていることの確認
        not_masked_row_index = 2
        assert list(df_masked["user_id"]) == ["FF", "AA", df_original.iloc[not_masked_row_index][("user_id", "")]]
        assert list(df_masked["username"]) == ["FF", "AA", df_original.iloc[not_masked_row_index][("username", "")]]
        assert list(df_masked["account_id"]) == ["FF", "AA", df_original.iloc[not_masked_row_index][("account_id", "")]]
        assert list(df_masked["biography"]) == [
            "category-TD",
            "category-TD",
            df_original.iloc[not_masked_row_index][("biography", "")],
        ]

    def test_create_masked_user_info_df__not_masked_user_id_set引数を指定する(self):
        df_original = read_multiheader_csv(str(data_dir / "user2.csv"), header_row_count=2)
        df_masked = create_masked_user_info_df(df_original, not_masked_user_id_set={"alice"})

        # user_idが"alice"の行はマスクされていないこと、それ以外はマスクされていることの確認
        not_masked_row_index = 0
        assert list(df_masked["user_id"]) == [df_original.iloc[not_masked_row_index][("user_id", "")], "AA", "IK"]
        assert list(df_masked["username"]) == [df_original.iloc[not_masked_row_index][("username", "")], "AA", "IK"]
        assert list(df_masked["account_id"]) == [df_original.iloc[not_masked_row_index][("account_id", "")], "AA", "IK"]
        assert list(df_masked["biography"]) == [
            df_original.iloc[not_masked_row_index][("biography", "")],
            "category-TD",
            "category-TU",
        ]

    def test_create_masked_user_info_df__not_masked_user_id_setとnot_masked_biography_set引数を指定する(self):
        df_original = read_multiheader_csv(str(data_dir / "user2.csv"), header_row_count=2)
        df_masked = create_masked_user_info_df(df_original, not_masked_biography_set={"China"}, not_masked_user_id_set={"bob"})

        # user_idが"bob", biographyが"China"の行はマスクされていないこと、それ以外はマスクされていることの確認
        not_masked_row_indexes = [1, 2]
        assert list(df_masked["user_id"]) == ["FF", *list(df_original.iloc[not_masked_row_indexes][("user_id", "")])]
        assert list(df_masked["username"]) == ["FF", *list(df_original.iloc[not_masked_row_indexes][("username", "")])]
        assert list(df_masked["account_id"]) == [
            "FF",
            *list(df_original.iloc[not_masked_row_indexes][("account_id", "")]),
        ]
        assert list(df_masked["biography"]) == [
            "category-TD",
            *list(df_original.iloc[not_masked_row_indexes][("biography", "")]),
        ]

    def test_create_masked_user_info_df__user_idしかないCSVをマスクする(self):
        # ヘッダ２行のCSVを読み込む。ただし username, biography, account_id がないCSV
        df_original = read_multiheader_csv(str(data_dir / "user2.csv"), header_row_count=2)
        df_masked = create_masked_user_info_df(
            df_original,
            not_masked_biography_set={"China"},
            not_masked_user_id_set={"bob"},
        )
        # user_idが"bob", biographyが"China"の行はマスクされていないこと、それ以外はマスクされていることの確認
        not_masked_row_indexes = [1, 2]
        assert list(df_masked["user_id"]) == ["FF", *list(df_original.iloc[not_masked_row_indexes][("user_id", "")])]

    def test_create_masked_user_info_df__ヘッダが1行のCSVをマスクする(self):
        # ヘッダ1行のCSVを読み込む
        df_original = pandas.read_csv(str(data_dir / "user1.csv"))
        df_masked = create_masked_user_info_df(df_original)

        expected_masked_user_info = ["FF", "AA", "IK"]
        assert list(df_masked["user_id"]) == expected_masked_user_info
        assert list(df_masked["username"]) == expected_masked_user_info
        assert list(df_masked["account_id"]) == expected_masked_user_info
        assert list(df_masked["biography"]) == ["category-TD", "category-TD", "category-TU"]

        # ユーザー情報以外は変わっていないことの確認
        assert df_masked["task_count"].equals(df_original["task_count"])
