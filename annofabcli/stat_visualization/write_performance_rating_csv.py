import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import numpy
import pandas

import annofabcli
from annofabcli.common.cli import AbstractCommandLineWithoutWebapiInterface, get_list_from_args
from annofabcli.common.utils import print_csv, read_multiheader_csv
from annofabcli.statistics.csv import FILENAME_PEFORMANCE_PER_USER

logger = logging.getLogger(__name__)


@dataclass
class ResultDataframe:
    annotation_productivity: pandas.DataFrame
    inspection_acceptance_productivity: pandas.DataFrame
    quality_per_task: pandas.DataFrame
    quality_per_annotation: pandas.DataFrame


def join_annotation_productivity(
    df: pandas.DataFrame,
    df_performance: pandas.DataFrame,
    project_title: str,
    threshold_worktime: float,
    threshold_task_count: int,
) -> pandas.DataFrame:
    df_joined = df_performance
    df_joined = df_joined.set_index("user_id")

    df_joined = df_joined[
        (df_joined[("task_count", "annotation")] > threshold_task_count)
        | (df_joined[("prediction_actual_worktime_hour", "annotation")] >= threshold_worktime)
    ]
    df_tmp = df_joined[[("actual_worktime/annotation_count", "annotation")]]
    df_tmp.columns = pandas.MultiIndex.from_tuples([(project_title, "actual_worktime/annotation_count__annotation")])
    return df.join(df_tmp)


def join_inspection_acceptance_productivity(
    df: pandas.DataFrame,
    df_performance: pandas.DataFrame,
    project_title: str,
    threshold_worktime: float,
    threshold_task_count: int,
) -> pandas.DataFrame:
    def _join_inspection():
        if ("actual_worktime/annotation_count", "inspection") not in df_performance.columns:
            return df

        df_joined = df_performance[
            (df_performance[("task_count", "inspection")] > threshold_task_count)
            | (df_performance[("prediction_actual_worktime_hour", "inspection")] > threshold_worktime)
        ]
        df_joined.set_index("user_id", inplace=True)
        df_tmp = df_joined[[("actual_worktime/annotation_count", "inspection")]]
        df_tmp.columns = pandas.MultiIndex.from_tuples(
            [(project_title, "actual_worktime/annotation_count__inspection")]
        )
        return df.join(df_tmp)

    def _join_acceptance():
        if ("actual_worktime/annotation_count", "acceptance") not in df_performance.columns:
            return df

        df_joined = df_performance[
            (df_performance[("task_count", "acceptance")] > threshold_task_count)
            | (df_performance[("prediction_actual_worktime_hour", "acceptance")] > threshold_worktime)
        ]
        df_joined.set_index("user_id", inplace=True)
        df_tmp = df_joined[[("actual_worktime/annotation_count", "acceptance")]]
        df_tmp.columns = pandas.MultiIndex.from_tuples(
            [(project_title, "actual_worktime/annotation_count__acceptance")]
        )
        return df.join(df_tmp)

    df = _join_inspection()
    df = _join_acceptance()

    return df


def join_quality_per_task(
    df: pandas.DataFrame,
    df_performance: pandas.DataFrame,
    project_title: str,
    threshold_worktime: float,
    threshold_task_count: int,
) -> pandas.DataFrame:
    df_joined = df_performance
    df_joined = df_joined.set_index("user_id")

    df_joined = df_joined[
        (df_joined[("task_count", "annotation")] > threshold_task_count)
        | (df_joined[("prediction_actual_worktime_hour", "annotation")] > threshold_worktime)
    ]
    df_tmp = df_joined[[("rejected_count/task_count", "annotation")]]

    df_tmp.columns = pandas.MultiIndex.from_tuples([(project_title, "rejected_count/task_count")])
    return df.join(df_tmp)


def join_quality_per_annotation(
    df: pandas.DataFrame,
    df_performance: pandas.DataFrame,
    project_title: str,
    threshold_worktime: float,
    threshold_task_count: int,
) -> pandas.DataFrame:
    df_joined = df_performance
    df_joined = df_joined.set_index("user_id")

    df_joined = df_joined[
        (df_joined[("task_count", "annotation")] > threshold_task_count)
        | (df_joined[("prediction_actual_worktime_hour", "annotation")] > threshold_worktime)
    ]
    df_tmp = df_joined[[("pointed_out_inspection_comment_count/annotation_count", "annotation")]]

    df_tmp.columns = pandas.MultiIndex.from_tuples(
        [(project_title, "pointed_out_inspection_comment_count/annotation_count")]
    )
    return df.join(df_tmp)


def create_rating_df(
    df_user: pandas.DataFrame, target_dir: Path, threshold_worktime: float, threshold_task_count: int
) -> ResultDataframe:

    df_annotation_productivity = df_user
    df_inspection_acceptance_productivity = df_user
    df_quality_per_task = df_user
    df_quality_per_annotation = df_user

    for project_dir in target_dir.iterdir():
        if not project_dir.is_dir():
            continue

        csv = project_dir / FILENAME_PEFORMANCE_PER_USER
        project_title = project_dir.name
        if not csv.exists():
            logger.warning(f"{csv} は存在しないのでスキップします。")
            continue

        df_performance = read_multiheader_csv(str(csv), header_row_count=2)
        df_annotation_productivity = join_annotation_productivity(
            df_annotation_productivity,
            df_performance,
            project_title=project_title,
            threshold_worktime=threshold_worktime,
            threshold_task_count=threshold_task_count,
        )
        df_inspection_acceptance_productivity = join_inspection_acceptance_productivity(
            df_inspection_acceptance_productivity,
            df_performance,
            project_title=project_title,
            threshold_worktime=threshold_worktime,
            threshold_task_count=threshold_task_count,
        )
        df_quality_per_task = join_quality_per_task(
            df_quality_per_task,
            df_performance,
            project_title=project_title,
            threshold_worktime=threshold_worktime,
            threshold_task_count=threshold_task_count,
        )
        df_quality_per_annotation = join_quality_per_annotation(
            df_quality_per_annotation,
            df_performance,
            project_title=project_title,
            threshold_worktime=threshold_worktime,
            threshold_task_count=threshold_task_count,
        )

    return ResultDataframe(
        annotation_productivity=df_annotation_productivity.reset_index(),
        inspection_acceptance_productivity=df_inspection_acceptance_productivity.reset_index(),
        quality_per_task=df_quality_per_task.reset_index(),
        quality_per_annotation=df_quality_per_annotation.reset_index(),
    )


def output_csv(result: ResultDataframe, output_dir: Path):
    print_csv(result.annotation_productivity, str(output_dir / "annotation_productivity.csv"))
    print_csv(result.inspection_acceptance_productivity, str(output_dir / "inspection_acceptance_productivity.csv"))
    print_csv(result.quality_per_task, str(output_dir / "annotation_quality_per_task.csv"))
    print_csv(result.quality_per_annotation, str(output_dir / "annotation_quality_per_annotation.csv"))


def to_rank(series: pandas.Series) -> pandas.Series:
    quantile = list(series.quantile([0.25, 0.5, 0.75]))

    def _to_point(value):
        if numpy.isnan(value):
            return numpy.nan
        elif value < quantile[0]:
            return "A"
        elif quantile[0] <= value < quantile[1]:
            return "B"
        elif quantile[1] <= value < quantile[2]:
            return "C"
        elif quantile[2] <= value:
            return "D"
        else:
            return numpy.nan

    if len([v for v in series if not numpy.isnan(v)]) >= 4:
        return series.map(_to_point)
    else:
        return pandas.Series([numpy.nan] * len(series))


def to_deviation(series: pandas.Series, threshold_deviation_user_count: Optional[int] = None) -> pandas.Series:
    if series.count() == 0 or (
        threshold_deviation_user_count is not None and series.count() <= threshold_deviation_user_count
    ):
        return pandas.Series([numpy.nan] * len(series))
    else:
        std = series.std(ddof=0)
        mean = series.mean()
        if std != 0.0:
            return series.map(lambda x: (x - mean) / std * 10 + 50)
        else:
            return series.map(lambda x: 50 if not numpy.isnan(x) else numpy.nan)


def create_rank_df(df: pandas.DataFrame, user_id_set: Optional[Set[str]] = None) -> pandas.DataFrame:
    df_rank = df.copy()
    for col in df.columns[3:]:
        df_rank[col] = to_rank(df[col])

    if user_id_set is not None:
        return df_rank[df_rank[("user_id", "")].isin(user_id_set)]
    else:
        return df_rank


def create_deviation_df(
    df: pandas.DataFrame, threshold_deviation_user_count: Optional[int] = None, user_id_set: Optional[Set[str]] = None
) -> pandas.DataFrame:
    df_rank = df.copy()
    user_columns = df.columns[0:3]
    project_columns = df.columns[3:]
    for col in project_columns:
        df_rank[col] = to_deviation(df[col], threshold_deviation_user_count)

    df_rank["mean_of_deviation"] = df_rank[project_columns].mean(axis=1)
    df_rank["count_of_project"] = df_rank[project_columns].count(axis=1)
    df = df_rank[list(user_columns) + [("mean_of_deviation", ""), ("count_of_project", "")] + list(project_columns)]
    if user_id_set is not None:
        return df[df[("user_id", "")].isin(user_id_set)]
    else:
        return df


def create_basic_statistics_df(df: pandas.DataFrame) -> pandas.DataFrame:
    df_stat = df.describe().T
    return df_stat


def output_rank_csv(result: ResultDataframe, output_dir: Path, user_id_list: Optional[List[str]] = None):
    user_id_set: Optional[Set[str]] = set(user_id_list) if user_id_list is not None else None
    print_csv(
        create_rank_df(result.annotation_productivity, user_id_set=user_id_set),
        str(output_dir / "annotation_productivity_rank.csv"),
    )
    print_csv(
        create_rank_df(result.inspection_acceptance_productivity, user_id_set=user_id_set),
        str(output_dir / "inspection_acceptance_productivity_rank.csv"),
    )
    print_csv(
        create_rank_df(result.quality_per_task, user_id_set=user_id_set),
        str(output_dir / "annotation_quality_per_task_rank.csv"),
    )
    print_csv(
        create_rank_df(result.quality_per_annotation, user_id_set=user_id_set),
        str(output_dir / "annotation_quality_per_annotation_rank.csv"),
    )


def output_deviation_csv(
    result: ResultDataframe,
    output_dir: Path,
    threshold_deviation_user_count: Optional[int] = None,
    user_id_list: Optional[List[str]] = None,
):
    """
    偏差値に変換したものを出力する
    """
    user_id_set: Optional[Set[str]] = set(user_id_list) if user_id_list is not None else None
    print_csv(
        create_deviation_df(result.annotation_productivity, threshold_deviation_user_count, user_id_set=user_id_set),
        str(output_dir / "annotation_productivity_deviation.csv"),
    )
    print_csv(
        create_deviation_df(
            result.inspection_acceptance_productivity, threshold_deviation_user_count, user_id_set=user_id_set
        ),
        str(output_dir / "inspection_acceptance_productivity_deviation.csv"),
    )
    print_csv(
        create_deviation_df(result.quality_per_task, threshold_deviation_user_count, user_id_set=user_id_set),
        str(output_dir / "annotation_quality_per_task_deviation.csv"),
    )

    print_csv(
        create_deviation_df(result.quality_per_annotation, threshold_deviation_user_count, user_id_set=user_id_set),
        str(output_dir / "annotation_quality_per_annotation_deviation.csv"),
    )


def output_basic_statistics_by_project(result: ResultDataframe, output_dir: Path):
    """
    プロジェクトごとの基本統計情報を出力する。
    """
    to_csv_kwargs = {"index": True}

    print_csv(
        create_basic_statistics_df(result.annotation_productivity),
        str(output_dir / "annotation_productivity_summary.csv"),
        to_csv_kwargs=to_csv_kwargs,
    )
    print_csv(
        create_basic_statistics_df(result.inspection_acceptance_productivity),
        str(output_dir / "inspection_acceptance_productivity_summary.csv"),
        to_csv_kwargs=to_csv_kwargs,
    )
    print_csv(
        create_basic_statistics_df(result.quality_per_task),
        str(output_dir / "annotation_quality_per_task_summary.csv"),
        to_csv_kwargs=to_csv_kwargs,
    )
    print_csv(
        create_basic_statistics_df(result.quality_per_annotation),
        str(output_dir / "annotation_quality_per_annotation_summary.csv"),
        to_csv_kwargs=to_csv_kwargs,
    )


def create_user_df(target_dir: Path) -> pandas.DataFrame:
    """
    "メンバごとの生産性と品質.csv"から、ユーザのDataFrameを作成する。

    Args:
        target_dir:

    Returns:
        ユーザのDataFrame. columnは("username", ""), ("biography", "") , indexが"user_id"

    """
    all_user_list: List[Dict[str, Any]] = []
    for project_dir in target_dir.iterdir():
        if not project_dir.is_dir():
            continue

        csv = project_dir / FILENAME_PEFORMANCE_PER_USER
        if not csv.exists():
            logger.warning(f"{csv} は存在しないのでスキップします。")
            continue

        tmp_df_user = read_multiheader_csv(str(csv), header_row_count=2)[
            [("user_id", ""), ("username", ""), ("biography", "")]
        ]
        all_user_list.extend(tmp_df_user.to_dict("records"))

    index = pandas.MultiIndex.from_tuples([("user_id", ""), ("username", ""), ("biography", "")])
    df_user = pandas.DataFrame(all_user_list, columns=index)
    df_user.drop_duplicates(inplace=True)
    return df_user.sort_values("user_id").set_index("user_id")


class WritePerformanceRatingCsv(AbstractCommandLineWithoutWebapiInterface):
    def main(self) -> None:
        args = self.args

        target_dir: Path = args.dir
        user_id_list = get_list_from_args(args.user_id) if args.user_id is not None else None
        df_user = create_user_df(target_dir)

        result = create_rating_df(
            df_user,
            target_dir,
            threshold_worktime=args.threshold_worktime,
            threshold_task_count=args.threshold_task_count,
        )

        output_dir: Path = args.output_dir
        # output_csv(result, output_dir)
        output_rank_csv(result, output_dir, user_id_list=user_id_list)
        output_deviation_csv(
            result,
            output_dir,
            threshold_deviation_user_count=args.threshold_deviation_user_count,
            user_id_list=user_id_list,
        )
        output_basic_statistics_by_project(result, output_dir)


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument(
        "--dir",
        type=Path,
        required=True,
        help=f"プロジェクトディレクトリが存在するディレクトリを指定してください。プロジェクトディレクトリ内の`{FILENAME_PEFORMANCE_PER_USER}`というファイルを読み込みます。",
    )

    parser.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        help="評価対象のユーザのuser_idを指定してください。" "`file://`を先頭に付けると、user_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "--threshold_worktime",
        type=int,
        default=0,
        help="作業時間の閾値。この時間以下の作業者は除外する。`threshold_task_count`とはOR条件で絞り込まれる。",
    )
    parser.add_argument(
        "--threshold_task_count",
        type=int,
        default=0,
        help="作業したタスク数の閾値。このタスク数以下の作業者は除外する。`threshold_worktime`とはOR条件で絞り込まれる。",
    )
    parser.add_argument(
        "--threshold_deviation_user_count",
        type=int,
        help="偏差値を出す際、プロジェクト内の作業者がしきい値以下であれば、偏差値を算出しない。",
    )
    parser.add_argument("-o", "--output_dir", required=True, type=Path, help="出力ディレクトリ")

    parser.set_defaults(subcommand_func=main)


def main(args):
    WritePerformanceRatingCsv(args).main()


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "write_performance_rating_csv"
    subcommand_help = "プロジェクトごとユーザごとにパフォーマンスを評価できる複数のCSVを出力します。"
    description = "プロジェクトごとユーザごとにパフォーマンスを評価できる複数のCSVを出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=description)
    parse_args(parser)
