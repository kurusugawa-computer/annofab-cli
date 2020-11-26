import os
from pathlib import Path

import pandas

from annofabcli.common.utils import read_multiheader_csv
from annofabcli.experimental.mask_user_info import create_masked_name, create_masked_user_info_df

# プロジェクトトップに移動する
os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/../")

test_dir = Path("./tests/data/experimental")
out_dir = Path("./tests/out/experimental")


class TestMaskUserInfo:
    def test_create_masked_name(self):
        assert create_masked_name("abc") == "P"

    def test_create_masked_user_info_df(self):
        # ヘッダ２行のCSVを読み込む
        df = create_masked_user_info_df(read_multiheader_csv(test_dir / "user2.csv", header_row_count=2))
        print(df)

        df = create_masked_user_info_df(
            read_multiheader_csv(test_dir / "user2.csv", header_row_count=2),
            not_masked_biography_set={"China"},
            not_masked_user_id_set=None,
        )
        print(df)

        df = create_masked_user_info_df(
            read_multiheader_csv(test_dir / "user2.csv", header_row_count=2),
            not_masked_biography_set=None,
            not_masked_user_id_set={"alice"},
        )
        print(df)

        df = create_masked_user_info_df(
            read_multiheader_csv(test_dir / "user2.csv", header_row_count=2),
            not_masked_biography_set={"China"},
            not_masked_user_id_set={"chris"},
        )
        print(df)

    def test_create_masked_user_info_df2(self):
        # ヘッダ２行のCSVを読み込む。ただし username, biography, account_id がないCSV
        df = create_masked_user_info_df(
            read_multiheader_csv(test_dir / "user2_1.csv", header_row_count=2),
            not_masked_biography_set={"China"},
            not_masked_user_id_set={"chris"},
        )
        print(df)

    def test_create_masked_user_info_df3(self):
        # ヘッダ1行のCSVを読み込む
        df = create_masked_user_info_df(pandas.read_csv(str(test_dir / "user1.csv")))
        print(df)
