import csv
from datetime import date
from typing import List

import numpy as np
import pandas as pd


def print_time_list_from_work_time_list(
    user_id_list: List[str], df: pd.DataFrame, start_date: date, end_date: date
) -> pd.DataFrame:
    # 複数のproject_id分を合計
    total_df = pd.DataFrame(df.groupby(["user_name", "user_id", "date"], as_index=False).sum())

    # user_id を絞り込み
    contains_df = total_df[total_df["user_id"].str.contains("|".join(user_id_list), case=False)].copy()

    # 不要になったuser_id を削除
    del contains_df["user_id"]

    # 日付で絞り込み
    contains_df["date"] = pd.to_datetime(contains_df["date"]).dt.date
    total_df = contains_df[(contains_df["date"] >= start_date) & (contains_df["date"] <= end_date)].copy()

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
                total_df.replace({np.inf: "--", np.nan: "--"}),
                sum_by_date.replace({np.inf: "--", np.nan: "--"}),
                sum_by_name.replace({np.inf: "--", np.nan: "--"}),
                sum_all.replace({np.inf: "--", np.nan: "--"}),
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
    with open(csv_path, "a") as f:
        writer = csv.writer(f, delimiter=",")
        writer.writerow([])
        writer.writerow(id_list)
