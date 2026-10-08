import shutil
from pathlib import Path

import pandas
import pytest
from pandas.testing import assert_frame_equal

from annofabcli.__main__ import main
from annofabcli.common.user_info_mask import create_masked_name
from annofabcli.common.utils import read_multiheader_csv

data_dir = Path("./tests/data/stat_visualization")
out_dir = Path("./tests/out/stat_visualization")


class TestCommandLine:
    def test__mask_user_info(self):
        main(
            [
                "stat_visualization",
                "mask_user_info",
                "--dir",
                str(data_dir / "mask_visualization_dir/visualization1"),
                "--output_dir",
                str(out_dir / "mask_user_info-out"),
                "--minimal",
            ]
        )

    def test__merge(self):
        main(
            [
                "stat_visualization",
                "merge",
                "--dir",
                str(data_dir / "merge_visualization_dir/visualization1"),
                str(data_dir / "merge_visualization_dir/visualization1"),
                "--output_dir",
                str(out_dir / "merge-out"),
                "--minimal",
            ]
        )

    def test__summarize_whole_performance_csv(self, tmp_path):
        input_dir = tmp_path / "summarize_whole_performance_csv"
        shutil.copytree(data_dir / "summarize_whole_performance_csv", input_dir)

        main(
            [
                "stat_visualization",
                "summarize_whole_performance_csv",
                "--dir",
                str(input_dir),
                "--output",
                str(tmp_path / "summarize_whole_performance_csv-out.csv"),
            ]
        )

    def test_write_performance_rating_csv(self):
        main(
            [
                "stat_visualization",
                "write_performance_rating_csv",
                "--dir",
                str(data_dir / "write_performance_rating_csv"),
                "--output_dir",
                str(out_dir / "write_performance_rating_csv-out"),
            ]
        )

    @pytest.mark.parametrize("excluded", [False, True])
    def test_write_performance_rating_csv_masks_all_user_csvs(self, tmp_path, excluded):
        source_csv = data_dir / "write_performance_rating_csv/visualization1/メンバごとの生産性と品質.csv"
        users = read_multiheader_csv(str(source_csv), header_row_count=2)
        selected_id = users.iloc[0][("user_id", "")]
        for masked in (False, True):
            args = [
                "stat_visualization",
                "write_performance_rating_csv",
                "--dir",
                str(data_dir / "write_performance_rating_csv"),
                "--output_dir",
                str(tmp_path / ("masked" if masked else "original")),
                "--user_id",
                selected_id,
            ]
            if masked:
                args.append("--mask_user_info")
                if excluded:
                    args.extend(["--not_masked_user_id", selected_id])
            main(args)

        replacement = {create_masked_name(user_id): user_id for user_id in users["user_id"] if not excluded or user_id != selected_id}
        replacement.update({create_masked_name(value, prefix="category"): value for value in users["biography"].dropna()})
        original_files = list((tmp_path / "original").rglob("*.csv"))
        assert len(original_files) == 15
        for original_csv in original_files:
            masked_csv = tmp_path / "masked" / original_csv.relative_to(tmp_path / "original")
            assert masked_csv.exists()
            if original_csv.stem.endswith(("__original", "__deviation", "__rank")):
                original_df = read_multiheader_csv(str(original_csv), header_row_count=3)
                masked_df = read_multiheader_csv(str(masked_csv), header_row_count=3)
                assert_frame_equal(masked_df.replace(replacement), original_df)
                if original_csv.stem.endswith(("__deviation", "__rank")):
                    assert list(masked_df["user_id"]) == [selected_id if excluded else create_masked_name(selected_id)]
                if not excluded:
                    for name in ("user_id", "username", "biography"):
                        assert set(masked_df[name].dropna()).isdisjoint(set(original_df[name].dropna()))
            else:
                assert_frame_equal(pandas.read_csv(masked_csv), pandas.read_csv(original_csv))
