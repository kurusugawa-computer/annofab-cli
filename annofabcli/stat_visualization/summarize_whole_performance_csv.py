from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

import annofabcli
from annofabcli.common.cli import (
    get_json_from_args,
)
from annofabcli.statistics.visualization.dataframe.project_performance import ProjectPerformance
from annofabcli.statistics.visualization.model import ProductionVolumeColumn, TaskCompletionCriteria
from annofabcli.statistics.visualization.project_dir import ProjectDir

logger = logging.getLogger(__name__)


def create_custom_production_volume_list(cli_value: str) -> list[ProductionVolumeColumn]:
    """
    コマンドラインから渡された文字列を元に、独自の生産量を表す列情報を生成します。
    """
    dict_data = get_json_from_args(cli_value)

    column_list = dict_data["column_list"]
    custom_production_volume_list = [ProductionVolumeColumn(column["value"], column["name"]) for column in column_list]

    return custom_production_volume_list


def main(args: argparse.Namespace) -> None:
    root_dir: Path = args.dir
    # task_completion_criteriaは何でもよいので、とりあえずACCEPTANCE_COMPLETEDを指定
    project_dir_list = [ProjectDir(elm, task_completion_criteria=TaskCompletionCriteria.ACCEPTANCE_COMPLETED) for elm in root_dir.iterdir() if elm.is_dir()]

    custom_production_volume_list = create_custom_production_volume_list(args.custom_production_volume) if args.custom_production_volume is not None else None
    project_performance = ProjectPerformance.from_project_dirs(project_dir_list, custom_production_volume_list=custom_production_volume_list)
    project_performance.to_csv(args.output)


def parse_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dir",
        type=Path,
        required=True,
        help="プロジェクトディレクトリが存在するディレクトリを指定してください。",
    )

    parser.add_argument("-o", "--output", type=Path, required=True, help="出力先のファイルパスを指定します。")

    custom_production_volume_sample = {
        "column_list": [{"value": "video_duration_minute", "name": "動画長さ"}],
    }

    parser.add_argument(
        "--custom_production_volume",
        type=str,
        help=(f"プロジェクト独自の生産量をJSON形式で指定します。(例) ``{json.dumps(custom_production_volume_sample, ensure_ascii=False)}`` \n"),
    )

    parser.set_defaults(subcommand_func=main)

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "summarize_whole_performance_csv"
    subcommand_help = "``annofabcli statistics visualize`` コマンドの出力結果であるプロジェクトディレクトリから、プロジェクトごとの生産性や品質の一覧を出力します。。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description=subcommand_help)
    parse_args(parser)
    return parser
