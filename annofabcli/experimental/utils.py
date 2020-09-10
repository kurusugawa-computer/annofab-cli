import csv
from enum import Enum
from typing import List, Tuple

import numpy as np
import pandas as pd


class TimeUnitTarget(Enum):
    H = "h"
    M = "m"
    S = "s"


class FormatTarget(Enum):
    DETAILS = "details"
    TOTAL = "total"
    BY_NAME_TOTAL = "by_name_total"
    COLUMN_LIST = "column_list"
    COLUMN_LIST_PER_PROJECT = "column_list_per_project"


def timeunit_conversion(df: pd.DataFrame, time_unit: TimeUnitTarget = TimeUnitTarget.H) -> pd.DataFrame:
    if time_unit == TimeUnitTarget.H:
        df["worktime_actual"] = df["worktime_actual"] / 60
        df["worktime_monitored"] = df["worktime_monitored"] / 60
        df["worktime_planned"] = df["worktime_planned"] / 60
    elif time_unit == TimeUnitTarget.S:
        df["worktime_actual"] = df["worktime_actual"] * 60
        df["worktime_monitored"] = df["worktime_monitored"] * 60
        df["worktime_planned"] = df["worktime_planned"] * 60

    return df


def calc_df_total(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # 複数のproject_id分を合計
    del df["project_id"]
    del df["project_title"]
    df["user_biography"] = df["user_biography"].fillna("")
    total_df = pd.DataFrame(df.groupby(["user_name", "user_id", "date", "user_biography"], as_index=False).sum())

    # 合計を計算する
    sum_by_date = (
        total_df[["date", "worktime_planned", "worktime_actual", "worktime_monitored"]]
        .groupby(["date"], as_index=False)
        .sum()
    )
    sum_by_name = (
        total_df[["user_name", "worktime_planned", "worktime_actual", "worktime_monitored"]]
        .groupby(["user_name"], as_index=False)
        .sum()
    )
    sum_all = total_df[["worktime_planned", "worktime_actual", "worktime_monitored"]].sum().to_frame().transpose()

    # 比率を追加する
    sum_by_date["activity_rate"] = sum_by_date["worktime_actual"] / sum_by_date["worktime_planned"]
    sum_by_date["monitor_rate"] = sum_by_date["worktime_monitored"] / sum_by_date["worktime_actual"]

    sum_by_name["activity_rate"] = sum_by_name["worktime_actual"] / sum_by_name["worktime_planned"]
    sum_by_name["monitor_rate"] = sum_by_name["worktime_monitored"] / sum_by_name["worktime_actual"]

    sum_all["activity_rate"] = sum_all["worktime_actual"] / sum_all["worktime_planned"]
    sum_all["monitor_rate"] = sum_all["worktime_monitored"] / sum_all["worktime_actual"]

    total_df["activity_rate"] = total_df["worktime_actual"] / total_df["worktime_planned"]
    total_df["monitor_rate"] = total_df["worktime_monitored"] / total_df["worktime_actual"]

    return total_df, sum_by_date, sum_by_name, sum_all


def print_time_list_from_work_time_list(df: pd.DataFrame) -> pd.DataFrame:
    # 複数のproject_id分を合計
    total_df, sum_by_date, sum_by_name, sum_all = calc_df_total(df=df)
    # 不要になったuser_id を削除
    del total_df["user_id"]
    del total_df["user_biography"]
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
        .sort_values(
            ["date", "user_name"],
        )
        .loc[
            :,
            [
                "date",
                "user_name",
                "worktime_planned",
                "worktime_actual",
                "worktime_monitored",
                "activity_rate",
                "monitor_rate",
            ],
        ]
    )
    # indexをつける
    result = result.set_index(["date", "user_name"])
    # 整形
    result = result.stack(0).unstack(1, fill_value="✕").unstack(1, fill_value="✕")
    result[result.loc[:, pd.IndexSlice[:, ["activity_rate", "monitor_rate"]]] == "✕"] = "--"

    result.index = result.index.date

    # NaT と NaN を 書き換える
    result = result.rename(columns={np.nan: "総合計"}, index={pd.NaT: "合計"})

    return result


def print_byname_total_list(df: pd.DataFrame) -> pd.DataFrame:
    # 複数のproject_id分を合計
    _, _, sum_by_name, _ = calc_df_total(df=df)

    # 結果を合体する
    result = sum_by_name.round(2).replace({np.inf: "--", np.nan: "--"})
    return result


def print_total(df: pd.DataFrame) -> pd.DataFrame:
    # 複数のproject_id分を合計
    _, _, _, sum_all = calc_df_total(df=df)

    # 結果を合体する
    result = sum_all.round(2).replace({np.inf: "--", np.nan: "--"})
    return result


def create_column_list(df: pd.DataFrame) -> pd.DataFrame:
    total_df, _, _, _ = calc_df_total(df=df)

    # 結果を合体する
    result = (
        total_df[
            [
                "date",
                "user_id",
                "user_name",
                "user_biography",
                "worktime_planned",
                "worktime_actual",
                "worktime_monitored",
                "activity_rate",
                "monitor_rate",
            ]
        ]
        .round(2)
        .replace({np.inf: "--", np.nan: "--"})
    )
    return result


def create_column_list_per_project(df: pd.DataFrame) -> pd.DataFrame:
    df["user_biography"] = df["user_biography"].fillna("")
    df["activity_rate"] = df["worktime_actual"] / df["worktime_planned"]
    df["monitor_rate"] = df["worktime_monitored"] / df["worktime_actual"]
    # 出力対象の列を指定する
    result = (
        df[
            [
                "date",
                "project_id",
                "project_title",
                "user_id",
                "user_name",
                "user_biography",
                "worktime_planned",
                "worktime_actual",
                "worktime_monitored",
                "activity_rate",
                "monitor_rate",
                "working_description",
            ]
        ]
        .round(2)
        .replace({np.inf: "--", np.nan: "--"})
    )

    return result


def print_time_list_csv(print_time_list: list) -> None:
    for time_list in print_time_list:
        print(*time_list, sep=",")


def add_id_csv(csv_path: str, id_list: List[str]):
    id_list[0:0] = ["project_id"]

    with open(csv_path, mode="a", encoding="utf_8_sig", newline="\r\n") as f:
        writer = csv.writer(f, delimiter=",")
        writer.writerow([])
        writer.writerow(id_list)
