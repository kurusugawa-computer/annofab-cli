from __future__ import annotations

import argparse
import copy
import functools
import json
import logging
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

import annofabapi

import annofabcli.common.cli
from annofabcli.common.cli import PARALLELISM_CHOICES, ArgumentParser, CommandLine, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.exceptions import AnnofabCliException
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class GetAnnotationMain:
    def __init__(self, service: annofabapi.Resource, project_id: str) -> None:
        self.service = service
        """Annofab APIクライアント。"""
        self.project_id = project_id
        """取得対象のプロジェクトID。"""

    def get_annotation_for_input_data(self, task_id: str, input_data_id: str, task_dir: Path) -> None:
        """Simpleアノテーションと参照先の外部ファイルを保存する。

        Args:
            task_id: 対象のタスクID。
            input_data_id: 対象の入力データID。
            task_dir: タスクの保存先ディレクトリ。

        Returns:
            None。
        """
        annotation, _ = self.service.api.get_annotation(self.project_id, task_id, input_data_id)
        outer_annotation_ids: set[str] = set()
        for detail in annotation["details"]:
            data = detail["data"]
            if data is not None and ("data_uri" in data or (data["_type"] == "Unknown" and data["data"].startswith("./"))):
                outer_annotation_ids.add(detail["annotation_id"])

        if outer_annotation_ids:
            # getAnnotationでは外部ファイルのURLを取得できないため、必要な場合のみエディタ用APIを併用する。
            editor_annotation, _ = self.service.api.get_editor_annotation(self.project_id, task_id, input_data_id, query_params={"v": "2"})
            outer_details = {detail["annotation_id"]: detail for detail in editor_annotation["details"] if detail["body"]["_type"] == "Outer"}
            outer_dir = task_dir / input_data_id
            outer_dir.mkdir()
            for annotation_id in sorted(outer_annotation_ids):
                self.service.wrapper.download(outer_details[annotation_id]["body"]["url"], outer_dir / annotation_id)

        (task_dir / f"{input_data_id}.json").write_text(json.dumps(annotation, ensure_ascii=False), encoding="utf-8")

    def get_annotation_for_task(self, task_id: str, output_dir: Path) -> None:
        """1タスクのアノテーションをZIPと同じ構成で保存する。

        Args:
            task_id: 対象のタスクID。
            output_dir: 配下にタスクIDのディレクトリを作成する出力先。

        Returns:
            None。
        """
        task_dir = output_dir / task_id
        if task_dir.exists():
            raise FileExistsError(f"保存先'{task_dir}'が既に存在します。別の出力先を指定してください。")

        task, _ = self.service.api.get_task(self.project_id, task_id)
        input_data_ids = task["input_data_id_list"]
        logger.info(f"タスク'{task_id}'の入力データ{len(input_data_ids)}件のアノテーションを取得します。")
        output_dir.mkdir(parents=True, exist_ok=True)
        # 取得途中で失敗した場合、不完全なタスクディレクトリを残さない。
        with TemporaryDirectory(dir=output_dir) as temporary_dir:
            staging_dir = Path(temporary_dir) / task_id
            staging_dir.mkdir()
            for index, input_data_id in enumerate(input_data_ids, start=1):
                logger.debug(f"{index}件目: 入力データ'{input_data_id}'のアノテーションを取得します。")
                self.get_annotation_for_input_data(task_id, input_data_id, staging_dir)
                if index % 100 == 0:
                    logger.info(f"{index} / {len(input_data_ids)}件の入力データのアノテーションを取得しました。")
            staging_dir.rename(task_dir)
        logger.info(f"{len(input_data_ids)}件の入力データのアノテーションを'{task_dir}'に保存しました。")

    def get_annotation_for_task_wrapper(self, task: tuple[int, str], output_dir: Path, *, copy_service: bool = False) -> bool:
        """タスクの取得結果を返し、失敗しても他のタスクの処理を継続する。

        Args:
            task: ゼロ始まりの処理順とタスクID。
            output_dir: 出力先ディレクトリ。
            copy_service: 並列処理でAPIクライアントを共有しないために複製するかどうか。

        Returns:
            タスクの取得に成功したかどうか。
        """
        index, task_id = task
        logger.info(f"{index + 1}件目: タスク'{task_id}'のアノテーションを取得します。")
        try:
            main_obj = GetAnnotationMain(copy.deepcopy(self.service), self.project_id) if copy_service else self
            main_obj.get_annotation_for_task(task_id, output_dir)
        except Exception:
            logger.warning(f"タスク'{task_id}'のアノテーションの取得に失敗しました。", exc_info=True)
            return False
        else:
            return True

    def get_annotation(self, task_ids: Iterable[str], output_dir: Path, *, parallelism: int | None = None) -> None:
        """複数タスクのアノテーションを取得し、必要に応じてタスク単位で並列化する。

        Args:
            task_ids: 取得対象のタスクID。重複するIDは1回だけ取得する。
            output_dir: タスクIDごとのディレクトリを作成する出力先。
            parallelism: 同時に取得するタスク数。Noneの場合は逐次処理する。

        Returns:
            None。

        Raises:
            AnnofabCliException: 1件以上のタスクの取得に失敗した場合。
        """
        unique_task_ids = list(dict.fromkeys(task_ids))
        logger.info(f"タスク{len(unique_task_ids)}件のアノテーションを取得します。")
        output_dir.mkdir(parents=True, exist_ok=True)
        func = functools.partial(self.get_annotation_for_task_wrapper, output_dir=output_dir, copy_service=parallelism is not None)
        success_count = 0
        if parallelism is None:
            success_count = sum(func(task) for task in enumerate(unique_task_ids))
        else:
            with ThreadPoolExecutor(max_workers=parallelism) as executor:
                success_count = sum(executor.map(func, enumerate(unique_task_ids)))
        failure_count = len(unique_task_ids) - success_count
        logger.info(f"タスクのアノテーション取得が完了しました。成功{success_count}件、失敗{failure_count}件。")
        if failure_count:
            raise AnnofabCliException(f"{failure_count}件のタスクのアノテーション取得に失敗しました。")


class GetAnnotation(CommandLine):
    def main(self) -> None:
        args = self.args
        super().require_project_access(args.project_id, project_member_roles=None)
        GetAnnotationMain(self.service, args.project_id).get_annotation(get_list_from_args(args.task_id), args.output_dir, parallelism=args.parallelism)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    GetAnnotation(service, AnnofabApiFacade(service), args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_task_id()
    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリ。配下にタスクIDのディレクトリを作成します。既存のタスクディレクトリは上書きしません。")
    parser.add_argument("--parallelism", type=int, choices=PARALLELISM_CHOICES, help="同時に取得するタスク数。指定しない場合は逐次処理します。各タスク内の入力データは逐次処理します。")
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction | None = None) -> argparse.ArgumentParser:
    description = "指定したタスクのアノテーションを、アノテーションZIPと同じディレクトリ構成・JSON形式で取得します。"
    parser = annofabcli.common.cli.add_parser(subparsers, "get", description, description)
    parse_args(parser)
    return parser
