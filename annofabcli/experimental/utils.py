import csv
from typing import List

import numpy as np
import pandas as pd


def print_time_list_from_work_time_list(df: pd.DataFrame) -> pd.DataFrame:
    # 複数のproject_id分を合計
    total_df = pd.DataFrame(df.groupby(["user_name", "user_id", "date"], as_index=False).sum())

    # 不要になったuser_id を削除
    del total_df["user_id"]

    # 合計を計算する
    sum_by_date = total_df[["date", "aw_plans", "aw_results", "af_time"]].groupby(["date"], as_index=False).sum()
    sum_by_name = (
        total_df[["user_name", "aw_plans", "aw_results", "af_time"]].groupby(["user_name"], as_index=False).sum()
    )
    sum_all = total_df[["aw_plans", "aw_results", "af_time"]].sum().to_frame().transpose()

    # 比率を追加する
    sum_by_date["result_per"] = sum_by_date["aw_results"] / sum_by_date["aw_plans"]
    sum_by_date["awaf_per"] = sum_by_date["aw_results"] / sum_by_date["af_time"]

    sum_by_name["result_per"] = sum_by_name["aw_results"] / sum_by_name["aw_plans"]
    sum_by_name["awaf_per"] = sum_by_name["aw_results"] / sum_by_name["af_time"]

    sum_all["result_per"] = sum_all["aw_results"] / sum_all["aw_plans"]
    sum_all["awaf_per"] = sum_all["aw_results"] / sum_all["af_time"]

    total_df["result_per"] = total_df["aw_results"] / total_df["aw_plans"]
    total_df["awaf_per"] = total_df["aw_results"] / total_df["af_time"]

    # 結果を合体する
    result = (
        pd.concat(
            [
                total_df.round(2).replace({np.inf: "--", np.nan: "--"}),
                sum_by_date.round(2).replace({np.inf: "--", np.nan: "--"}),
                sum_by_name.round(2).replace({np.inf: "--", np.nan: "--"}),
                sum_all.round(2).replace({np.inf: "--", np.nan: "--"}),
            ],
            sort=False,
        )
        .sort_values(["date", "user_name"],)
        .loc[:, ["date", "user_name", "aw_plans", "aw_results", "af_time", "result_per", "awaf_per"]]
    )
    # indexをつける
    result = result.set_index(["date", "user_name"])
    # 整形
    result = result.stack(0).unstack(1, fill_value="✕").unstack(1, fill_value="✕")
    result[result.loc[:, pd.IndexSlice[:, ["result_per", "awaf_per"]]] == "✕"] = "--"

    result.index = result.index.date

    # NaT と NaN を 書き換える
    result = result.rename(columns={np.nan: "総合計"}, index={pd.NaT: "合計"})

    return result


def print_time_list_csv(print_time_list: list) -> None:
    for time_list in print_time_list:
        print(*time_list, sep=",")


def add_id_csv(csv_path: str, id_list: List[str]):
    id_list[0:0] = ["project_id"]
    with open(csv_path, mode="a", encoding="utf_8_sig") as f:
        writer = csv.writer(f, delimiter=",")
        writer.writerow([])
        writer.writerow(id_list)
