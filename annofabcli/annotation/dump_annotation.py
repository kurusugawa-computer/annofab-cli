from __future__ import annotations

import argparse
import functools
import json
import logging
import multiprocessing
from pathlib import Path
from typing import List, Optional

import annofabapi
from annofabapi.models import AnnotationDataHoldingType

import annofabcli
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class DumpAnnotationMain:
    def __init__(self, service: annofabapi.Resource, project_id: str):
        self.service = service
        self.facade = AnnofabApiFacade(service)
        self.project_id = project_id

    def dump_annotation_for_input_data(self, task_id: str, input_data_id: str, task_dir: Path) -> None:
        annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id, input_data_id)
        json_path = task_dir / f"{input_data_id}.json"
        json_path.write_text(json.dumps(annotation, ensure_ascii=False), encoding="utf-8")

        details = annotation["details"]
        outer_details = [e for e in details if e["data_holding_type"] == AnnotationDataHoldingType.OUTER.value]
        if len(outer_details) == 0:
            return

        outer_dir = task_dir / input_data_id
        outer_dir.mkdir(exist_ok=True, parents=True)

        # 塗りつぶし画像など外部リソースに保存されているファイルをダウンロードする
        for detail in outer_details:
            annotation_id = detail["annotation_id"]
            outer_file_path = outer_dir / f"{annotation_id}"
            self.service.wrapper.download(detail["url"], outer_file_path)

    def dump_annotation_for_task(self, task_id: str, output_dir: Path, *, task_index: Optional[int] = None) -> bool:
        """
        タスク配下のアノテーションをファイルに保存する。

        Args:
            task_id:
            output_dir: 保存先。配下に"task_id"のディレクトリを作成する。

        Returns:
            アノテーション情報をファイルに保存したかどうか。
        """
        logger_prefix = f"{str(task_index+1)} 件目: " if task_index is not None else ""
        task = self.service.wrapper.get_task_or_none(self.project_id, task_id)
        if task is None:
            logger.warning(f"task_id = '{task_id}' のタスクは存在しません。スキップします。")
            return False

        input_data_id_list = task["input_data_id_list"]
        task_dir = output_dir / task_id
        task_dir.mkdir(exist_ok=True, parents=True)
        logger.debug(f"{logger_prefix}task_id = '{task_id}' のアノテーション情報を '{task_dir}' ディレクトリに保存します。")

        is_failure = False
        for input_data_id in input_data_id_list:
            try:
                self.dump_annotation_for_input_data(task_id, input_data_id, task_dir=task_dir)
            except Exception:
                logger.warning(f"タスク'{task_id}', 入力データ'{input_data_id}' のアノテーション情報のダンプに失敗しました。", exc_info=True)
                is_failure = True
                continue

        return not is_failure

    def dump_annotation_for_task_wrapper(self, tpl: tuple[int, str], output_dir: Path) -> bool:
        task_index, task_id = tpl
        try:
            return self.dump_annotation_for_task(task_id, output_dir=output_dir, task_index=task_index)
        except Exception:  # pylint: disable=broad-except
            logger.warning(f"タスク'{task_id}'のアノテーション情報のダンプに失敗しました。", exc_info=True)
            return False

    def dump_annotation(self, task_id_list: List[str], output_dir: Path, parallelism: Optional[int] = None):
        project_title = self.facade.get_project_title(self.project_id)
        logger.info(f"プロジェクト'{project_title}'に対して、タスク{len(task_id_list)} 件のアノテーションをファイルに保存します。")

        output_dir.mkdir(exist_ok=True, parents=True)

        success_count = 0

        if parallelism is not None:
            func = functools.partial(self.dump_annotation_for_task_wrapper, output_dir=output_dir)
            with multiprocessing.Pool(parallelism) as pool:
                result_bool_list = pool.map(func, enumerate(task_id_list))
                success_count = len([e for e in result_bool_list if e])

        else:
            for task_index, task_id in enumerate(task_id_list):
                try:
                    result = self.dump_annotation_for_task(task_id, output_dir=output_dir, task_index=task_index)
                    if result:
                        success_count += 1
                except Exception:
                    logger.warning(f"タスク'{task_id}'のアノテーション情報のダンプに失敗しました。", exc_info=True)

        logger.info(f"{success_count} / {len(task_id_list)} 件のタスクのアノテーション情報をダンプしました。")


class DumpAnnotation(AbstractCommandLineInterface):
    """
    アノテーション情報をダンプする
    """

    def main(self):
        args = self.args
        project_id = args.project_id
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        output_dir = Path(args.output_dir)

        super().validate_project(project_id, project_member_roles=None)

        main_obj = DumpAnnotationMain(self.service, project_id)
        main_obj.dump_annotation(task_id_list, output_dir=output_dir, parallelism=args.parallelism)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DumpAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    parser.add_argument("-o", "--output_dir", type=str, required=True, help="出力先ディレクトリのパス")

    parser.add_argument(
        "--parallelism",
        type=int,
        help="並列度。指定しない場合は、逐次的に処理します。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None):
    subcommand_name = "dump"
    subcommand_help = "アノテーション情報をファイルに保存します。"
    description = "指定したタスク配下のアノテーション情報をディレクトリに保存します。アノテーションをバックアップしたいときなどに利用できます。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
