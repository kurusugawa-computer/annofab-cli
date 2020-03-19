import argparse
import json
import logging
from pathlib import Path
from typing import List

import requests
from annofabapi.models import AnnotationDataHoldingType

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class DumpAnnotation(AbstractCommandLineInterface):
    """
    アノテーション情報をダンプする
    """

    def dump_annotation_for_input_data(self, project_id: str, task_id: str, input_data_id: str, task_dir: Path) -> None:
        annotation, _ = self.service.api.get_editor_annotation(project_id, task_id, input_data_id)
        json_path = task_dir / f"{input_data_id}.json"
        json_path.write_text(json.dumps(annotation, ensure_ascii=False), encoding="utf-8")

        details = annotation["details"]
        outer_details = [e for e in details if e["data_holding_type"] == AnnotationDataHoldingType.OUTER.value]
        if len(outer_details) == 0:
            return

        outer_dir = task_dir / input_data_id
        outer_dir.mkdir(exist_ok=True, parents=True)

        for detail in outer_details:
            if not detail["data_holding_type"] == AnnotationDataHoldingType.OUTER.value:
                continue

            outer_file_url = detail["url"]
            response = self.service.api.session.get(outer_file_url)
            if response.status_code != requests.codes.ok:
                logger.warning(
                    f"塗りつぶし画像ファイルのダウンロード失敗しました。"
                    f"status_code={response.status_code}, url={response.url}, text={response.text}"
                )
                continue

            annotation_id = detail["annotation_id"]
            outer_file_path = outer_dir / f"{annotation_id}"
            outer_file_path.write_bytes(response.content)

    def dump_annotation_for_task(self, project_id: str, task_id: str, output_dir: Path) -> bool:
        """
        タスク配下のアノテーションをファイルに保存する。

        Args:
            project_id:
            task_id:
            output_dir: 保存先。配下に"task_id"のディレクトリを作成する。

        Returns:
            アノテーション情報をファイルに保存したかどうか。
        """
        task = self.service.wrapper.get_task_or_none(project_id, task_id)
        if task is None:
            logger.warning(f"task_id = '{task_id}' のタスクは存在しません。スキップします。")
            return False

        input_data_id_list = task["input_data_id_list"]
        task_dir = output_dir / task_id
        task_dir.mkdir(exist_ok=True, parents=True)
        logger.debug(f"task_id = '{task_id}' のアノテーション情報を '{task_dir}' ディレクトリに保存します。")
        for input_data_id in input_data_id_list:
            self.dump_annotation_for_input_data(project_id, task_id, input_data_id, task_dir=task_dir)

        return True

    def dump_annotation(self, project_id: str, task_id_list: List[str], output_dir: Path):
        super().validate_project(project_id, project_member_roles=None)

        project_title = self.facade.get_project_title(project_id)
        logger.info(f"プロジェクト'{project_title}'に対して、タスク{len(task_id_list)} 件のアノテーションをファイルに保存します。")

        output_dir.mkdir(exist_ok=True, parents=True)

        for task_id in task_id_list:
            self.dump_annotation_for_task(project_id, task_id, output_dir=output_dir)

        logger.info(f"処理が完了しました。")

    def main(self):
        args = self.args
        project_id = args.project_id
        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id)
        output_dir = Path(args.output_dir)
        self.dump_annotation(project_id, task_id_list, output_dir=output_dir)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DumpAnnotation(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()
    argument_parser.add_task_id()

    parser.add_argument("-o", "--output_dir", type=str, required=True, help="出力先ディレクトリのパス")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "dump"
    subcommand_help = "アノテーション情報をファイルに保存します。"
    description = "指定したタスク配下のアノテーション情報をディレクトリに保存します。アノテーションをバックアップしたいときなどに利用できます。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
