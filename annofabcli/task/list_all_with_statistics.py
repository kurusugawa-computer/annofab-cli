from __future__ import annotations

import argparse
import json
import logging
import tempfile
from collections.abc import Collection
from pathlib import Path
from typing import Any

import pandas
from annofabapi.models import InputDataType, ProjectMemberRole

import annofabcli.common.cli
from annofabcli.common.annotation_production_volume import aggregate_annotation_production_volume
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login, get_json_from_args, get_list_from_args
from annofabcli.common.enums import OutputFormat
from annofabcli.common.facade import AnnofabApiFacade, TaskQuery
from annofabcli.common.utils import print_csv, print_json
from annofabcli.common.video_duration import get_task_video_duration_list
from annofabcli.statistics.visualization.annotation_count_api import AnnotationCountSource, count_annotations_from_api, resolve_annotation_count_source
from annofabcli.task.list_all_tasks_added_task_history import ListAllTasksAddedTaskHistoryMain
from annofabcli.task.list_tasks_added_task_history import TasksAddedTaskHistoryOutput

logger = logging.getLogger(__name__)

PRODUCTION_VOLUME_COLUMNS = ["annotation_count", "video_duration_minute", "annotation_duration_minute"]
"""履歴付きタスク一覧に追加する生産量の列。"""


def get_output_columns() -> list[str]:
    """CSVとJSONに出力する固定列を取得します。

    Args:
        なし。

    Returns:
        入力データ数の直後に生産量3列を追加した、47列の一覧。
    """
    columns = TasksAddedTaskHistoryOutput._get_output_target_columns()  # noqa: SLF001
    index = columns.index("input_data_count") + 1
    return columns[:index] + PRODUCTION_VOLUME_COLUMNS + columns[index:]


def output_tasks(task_list: list[dict[str, Any]], output: Path | None, output_format: OutputFormat) -> None:
    """タスク一覧を固定列とメタデータに限定して出力します。

    Args:
        task_list: 統計情報を付加したタスク一覧。
        output: 出力先。Noneなら標準出力。
        output_format: CSVまたはJSON。

    Returns:
        なし。
    """
    columns = get_output_columns()
    rows = [{**{column: task.get(column) for column in columns}, "metadata": task.get("metadata") or {}} for task in task_list]
    if output_format == OutputFormat.CSV:
        csv_rows = [{key: json.dumps(value, ensure_ascii=False) if key.endswith("_worktime_hour_by_user") else value for key, value in row.items()} for row in rows]
        df = pandas.json_normalize(csv_rows)
        metadata_columns = sorted(column for column in df.columns if column.startswith("metadata."))
        df = df.reindex(columns=columns + metadata_columns).astype({"annotation_count": "Int64"})
        print_csv(df, output=output)
    else:
        print_json(rows, output=output, is_pretty=output_format == OutputFormat.PRETTY_JSON)


class ListAllWithStatisticsMain(ListAllTasksAddedTaskHistoryMain):
    """全件ファイルを基にタスクごとの作業時間と生産量を取得します。"""

    def get_tasks(
        self,
        temp_dir: Path,
        *,
        task_id_list: list[str] | None = None,
        task_query: TaskQuery | None = None,
        latest: bool = False,
        get_task_histories_one_of_each: bool = False,
    ) -> list[dict[str, Any]]:
        """対象タスクを絞り込み、全件ファイルまたはAPIの履歴を付加します。

        Args:
            temp_dir: ダウンロード先。
            task_id_list: 対象タスクID。
            task_query: タスクの絞り込み条件。
            latest: タスク全件ファイルを更新するか。
            get_task_histories_one_of_each: 全件ファイルの更新を待たず、対象タスクの履歴をAPIで取得するか。

        Returns:
            履歴情報を付加したタスク一覧。
        """
        tasks = self.filter_task_list(self.load_task_list(temp_dir, is_latest=latest), task_id_list=task_id_list, task_query=task_query)
        if not tasks:
            return []
        if get_task_histories_one_of_each:
            logger.info(f"全件ファイルの更新前の作業時間を確認するため、対象{len(tasks)}件のタスク履歴をWebAPIで1件ずつ取得します。")
            histories = {}
            for index, task in enumerate(tasks, start=1):
                logger.debug(f"{index}/{len(tasks)}件目: task_id='{task['task_id']}'の履歴を取得します。")
                histories[task["task_id"]] = self.service.api.get_task_histories(self.project_id, task["task_id"])[0]
                if index % 100 == 0:
                    logger.info(f"タスク履歴を{index}/{len(tasks)}件取得しました。")
            logger.info(f"タスク履歴の取得が完了しました。成功{len(histories)}件。")
        else:
            logger.info("作業時間はタスク履歴全件ファイルの時点の情報です。更新前に確認する場合は --get_task_histories_one_of_each を指定してください。")
            histories = self.load_task_history_dict(temp_dir)
        tasks = self.get_detail_task_list(tasks, histories)
        if get_task_histories_one_of_each:
            for task in tasks:
                task["worktime_hour"] = sum(task[f"{phase}_worktime_hour"] for phase in ["annotation", "inspection", "acceptance"])
        return tasks

    def add_statistics(
        self,
        tasks: list[dict[str, Any]],
        temp_dir: Path,
        *,
        annotation_count_source: AnnotationCountSource,
        latest: bool = False,
        include_labels: Collection[str] | None = None,
        exclude_labels: Collection[str] | None = None,
    ) -> None:
        """対象タスクにアノテーション数、動画時間、区間長さを付加します。

        Args:
            tasks: 生産量を付加するタスク一覧。
            temp_dir: ダウンロード先。
            annotation_count_source: 件数の取得元。
            latest: アノテーションZIPと入力データ全件ファイルを更新するか。
            include_labels: 集計対象ラベル名（英語）。
            exclude_labels: 集計対象外ラベル名（英語）。

        Returns:
            なし。
        """
        if not tasks:
            return
        project, _ = self.service.api.get_project(self.project_id)
        is_movie = project["input_data_type"] == InputDataType.MOVIE.value
        source = resolve_annotation_count_source(self.service, self.project_id, annotation_count_source)
        for task in tasks:
            task.update(dict.fromkeys(PRODUCTION_VOLUME_COLUMNS))

        if source == AnnotationCountSource.ZIP or is_movie:
            annotation_zip = self.downloading_obj.download_annotation_zip_to_dir(self.project_id, temp_dir, is_latest=latest)
            volumes = aggregate_annotation_production_volume(
                annotation_zip,
                task_ids={task["task_id"] for task in tasks},
                include_labels=include_labels,
                exclude_labels=exclude_labels,
                calculate_duration=is_movie,
            )
            for task in tasks:
                volume = volumes.get(task["task_id"])
                if volume is None:
                    logger.warning(f"task_id='{task['task_id']}'のアノテーションJSONがZIPに存在しないため、生産量を空欄にします。")
                    continue
                if source == AnnotationCountSource.ZIP:
                    task["annotation_count"] = volume.annotation_count
                if is_movie:
                    task["annotation_duration_minute"] = volume.annotation_duration_minute

        if source == AnnotationCountSource.API:
            annotation_count = count_annotations_from_api(self.service, self.project_id, tasks, include_labels=include_labels, exclude_labels=exclude_labels)
            counts = dict(zip(annotation_count.df["task_id"], annotation_count.df["annotation_count"], strict=True))
            for task in tasks:
                task["annotation_count"] = counts[task["task_id"]]

        if is_movie:
            input_data_json = self.downloading_obj.download_input_data_json_to_dir(self.project_id, temp_dir, is_latest=latest)
            input_data_list = json.loads(input_data_json.read_text(encoding="utf-8"))
            for task, duration in zip(tasks, get_task_video_duration_list(tasks, input_data_list), strict=True):
                seconds = duration["video_duration_second"]
                task["video_duration_minute"] = seconds / 60 if seconds is not None else None


class ListAllWithStatistics(CommandLine):
    """タスクごとの作業時間と生産量を出力するコマンド。"""

    def main(self) -> None:
        """必要な全件ファイルと履歴を取得して一覧を出力します。

        Args:
            なし。

        Returns:
            なし。
        """
        args = self.args
        self.require_project_access(args.project_id, [ProjectMemberRole.OWNER, ProjectMemberRole.TRAINING_DATA_USER])
        task_ids = get_list_from_args(args.task_id) if args.task_id is not None else None
        query = TaskQuery.from_dict(get_json_from_args(args.task_query)) if args.task_query is not None else None
        include_labels = get_list_from_args(args.production_volume_include_label) if args.production_volume_include_label is not None else None
        exclude_labels = get_list_from_args(args.production_volume_exclude_label) if args.production_volume_exclude_label is not None else None
        main_obj = ListAllWithStatisticsMain(self.service, args.project_id)
        with tempfile.TemporaryDirectory() as temporary_dir:
            temp_dir = Path(args.temp_dir) if args.temp_dir is not None else Path(temporary_dir)
            temp_dir.mkdir(parents=True, exist_ok=True)
            tasks = main_obj.get_tasks(temp_dir, task_id_list=task_ids, task_query=query, latest=args.latest, get_task_histories_one_of_each=args.get_task_histories_one_of_each)
            main_obj.add_statistics(
                tasks, temp_dir, annotation_count_source=AnnotationCountSource(args.annotation_count_source), latest=args.latest, include_labels=include_labels, exclude_labels=exclude_labels
            )
        output_tasks(tasks, args.output, OutputFormat(args.format))
        logger.info(f"タスク統計一覧の出力が完了しました。成功{len(tasks)}件。各データの取得時点は一致するとは限りません。")


def main(args: argparse.Namespace) -> None:
    """認証してコマンドを実行します。

    Args:
        args: コマンドライン引数。

    Returns:
        なし。
    """
    service = build_annofabapi_resource_and_login(args)
    ListAllWithStatistics(service, AnnofabApiFacade(service), args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    """タスク統計一覧の引数を登録します。

    Args:
        parser: 引数パーサー。

    Returns:
        なし。
    """
    arguments = ArgumentParser(parser)
    arguments.add_project_id()
    arguments.add_task_id(required=False)
    arguments.add_task_query()
    parser.add_argument(
        "--latest",
        action="store_true",
        help="タスク・入力データ全件ファイルとアノテーションZIPのうち、使用するファイルを更新します。数分から数十分待つ場合があります。タスク履歴全件ファイルは更新されません。",
    )
    parser.add_argument(
        "--get_task_histories_one_of_each",
        action="store_true",
        help="タスク履歴全件ファイルが更新される前に作業時間を確認したい場合に指定します。絞り込み後の各タスクの最新履歴をWebAPIで1件ずつ取得します。対象タスク数だけAPIを実行するため、処理時間が長くなります。",
    )
    parser.add_argument("--temp_dir", type=Path, help="ダウンロードした全件ファイルとアノテーションZIPの保存先ディレクトリ。")
    parser.add_argument(
        "--annotation_count_source",
        choices=[source.value for source in AnnotationCountSource],
        default=AnnotationCountSource.AUTO.value,
        help="アノテーション数の取得元。autoは3Dセグメントのラベルがあればapi、それ以外はzipを選びます。apiは一覧APIの総件数を使用します。動画ではapi指定時も区間長さの集計用にZIPを取得します。",
    )
    label_group = parser.add_mutually_exclusive_group()
    for name, description in [("include", "含める"), ("exclude", "除外する")]:
        label_group.add_argument(
            f"--production_volume_{name}_label",
            nargs="+",
            help=f"アノテーション数と区間長さの集計対象に{description}ラベル名（英語）。複数指定できます。file://で改行区切りの一覧ファイルを1個だけ指定することもできます。作業時間・動画時間・入力データ数や対象タスクには影響しません。",
        )
    arguments.add_output()
    arguments.add_format(choices=[OutputFormat.CSV, OutputFormat.JSON, OutputFormat.PRETTY_JSON], default=OutputFormat.CSV)
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    """サブコマンドを登録します。

    Args:
        subparsers: 親コマンドのサブパーサー。

    Returns:
        登録した引数パーサー。
    """
    parser = annofabcli.common.cli.add_parser(
        subparsers,
        "list_all_with_statistics",
        "全タスクの作業時間・アノテーション数・動画時間・区間長さを出力します。",
        "全状態のタスクを対象に、履歴に関する情報と生産量をまとめた一覧を出力します。",
        epilog="アノテーションユーザ/オーナロールを持つユーザで実行してください。",
    )
    parse_args(parser)
    return parser
