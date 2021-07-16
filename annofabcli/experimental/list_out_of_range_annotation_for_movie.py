import argparse
import asyncio
import json
import logging
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import annofabapi
import pandas
from annofabapi.parser import SimpleAnnotationZipParser

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login
from annofabcli.common.download import DownloadingFile

logger = logging.getLogger(__name__)


def _millisecond_to_hour(millisecond: int):
    return millisecond / 1000 / 3600


def _get_time_range(str_data: str):
    tmp_list = str_data.split(",")
    return (int(tmp_list[0]), int(tmp_list[1]))


class ListOutOfRangeAnnotationForMovieMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service

    @staticmethod
    def get_max_seconds_for_webapi(annotation: Dict[str, Any]) -> Tuple[float, float]:
        details = annotation["details"]
        range_list = [_get_time_range(e["data"]) for e in details if e["data"] is not None]
        if len(range_list) == 0:
            return 0, 0
        else:
            max_begin = max([e[0] for e in range_list]) / 1000
            max_end = max([e[1] for e in range_list]) / 1000
            return max_begin, max_end

    @staticmethod
    def get_max_seconds_for_zip(annotation: Dict[str, Any]) -> Tuple[float, float]:
        details = annotation["details"]
        range_list = [(e["data"]["begin"], e["data"]["end"]) for e in details if e["data"]["_type"] == "Range"]
        if len(range_list) == 0:
            return 0, 0
        else:
            max_begin = max([e[0] for e in range_list]) / 1000
            max_end = max([e[1] for e in range_list]) / 1000
            return max_begin, max_end

    def create_dataframe(
        self,
        project_id: str,
        task_list: List[Dict[str, Any]],
        input_data_list: List[Dict[str, Any]],
        annotation_zip: Optional[Path],
    ) -> pandas.DataFrame:
        if annotation_zip is None:
            logger.info(f"{len(task_list)} 件のアノテーション情報をWebAPIで取得します。")
            for task_index, task in enumerate(task_list):
                task["worktime_hour"] = _millisecond_to_hour(task["work_time_span"])
                task["input_data_id"] = task["input_data_id_list"][0]
                annotation, _ = self.service.api.get_editor_annotation(
                    project_id, task["task_id"], task["input_data_id"]
                )
                max_seconds = self.get_max_seconds_for_webapi(annotation)
                task["max_begin_second"] = max_seconds[0]
                task["max_end_second"] = max_seconds[1]
                if (task_index + 1) % 100 == 0:
                    logger.info(f"{task_index+1} 件のアノテーション情報を取得しました。")
        else:
            logger.info(f"{len(task_list)} 件のアノテーション情報を {str(annotation_zip)} から取得します。")
            with zipfile.ZipFile(str(annotation_zip), "r") as zip_file:
                for task_index, task in enumerate(task_list):
                    task["worktime_hour"] = _millisecond_to_hour(task["work_time_span"])
                    task["input_data_id"] = task["input_data_id_list"][0]

                    parser = SimpleAnnotationZipParser(zip_file, f"{task['task_id']}/{task['input_data_id']}.json")
                    simple_annotation = parser.load_json()
                    max_seconds = self.get_max_seconds_for_zip(simple_annotation)
                    task["max_begin_second"] = max_seconds[0]
                    task["max_end_second"] = max_seconds[1]

                    if (task_index + 1) % 100 == 0:
                        logger.info(f"{task_index+1} 件のアノテーション情報を取得しました。")

        df_task = pandas.DataFrame(
            task_list,
            columns=[
                "task_id",
                "status",
                "phase",
                "worktime_hour",
                "max_begin_second",
                "max_end_second",
                "input_data_id",
            ],
        )
        df_input_data = pandas.DataFrame(input_data_list, columns=["input_data_id", "input_duration"])
        df_merged = pandas.merge(df_task, df_input_data, how="left", on="input_data_id")
        return df_merged

    @staticmethod
    def filter_task_list(task_list: List[Dict[str, Any]], task_id_list: List[str]) -> List[Dict[str, Any]]:
        def _exists(task_id) -> bool:
            if task_id in task_id_set:
                task_id_set.remove(task_id)
                return True
            else:
                return False

        task_id_set = set(task_id_list)
        task_list = [e for e in task_list if _exists(e["task_id"])]
        if len(task_id_set) > 0:
            tmp = "\n".join(task_id_set)
            logger.warning(f"以下のタスクは存在しません。\n{tmp}")
        return task_list

    def list_out_of_range_annotation_for_movie(
        self, project_id: str, task_id_list: Optional[List[str]], parse_annotation_zip: bool = False
    ) -> pandas.DataFrame:
        cache_dir = annofabcli.utils.get_cache_dir()
        downloading_obj = DownloadingFile(self.service)

        input_data_json_path = cache_dir / f"input_data-{project_id}.json"
        task_json_path = cache_dir / f"task-{project_id}.json"
        awaitable_list = [
            downloading_obj.download_task_json_with_async(project_id, dest_path=str(task_json_path)),
            downloading_obj.download_input_data_json_with_async(
                project_id,
                dest_path=str(input_data_json_path),
            ),
        ]

        annotation_zip_path = None
        if parse_annotation_zip:
            annotation_zip_path = cache_dir / f"annotation-{project_id}.zip"
            awaitable_list.append(
                downloading_obj.download_annotation_zip_with_async(
                    project_id,
                    dest_path=str(annotation_zip_path),
                )
            )

        gather = asyncio.gather(*awaitable_list)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(gather)

        with input_data_json_path.open() as f:
            input_data_list = json.load(f)

        with task_json_path.open() as f:
            task_list = json.load(f)
            if task_id_list is not None:
                task_list = self.filter_task_list(task_list, task_id_list)

        df = self.create_dataframe(
            project_id, task_list=task_list, input_data_list=input_data_list, annotation_zip=annotation_zip_path
        )
        return df


class ListOutOfRangeAnnotationForMovie(AbstractCommandLineInterface):
    def main(self):
        args = self.args

        task_id_list = annofabcli.common.cli.get_list_from_args(args.task_id) if args.task_id is not None else None
        main_obj = ListOutOfRangeAnnotationForMovieMain(self.service)
        df = main_obj.list_out_of_range_annotation_for_movie(args.project_id, task_id_list, args.parse_annotation_zip)
        self.print_csv(df)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListOutOfRangeAnnotationForMovie(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)
    argument_parser.add_project_id()
    argument_parser.add_task_id(required=False)
    argument_parser.add_output()

    parser.add_argument(
        "--parse_annotation_zip", action="store_true", help="アノテーションzipから範囲外のアノテーション情報を取得します。ただし、範囲外の終了時間は存在しません。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_out_of_range_annotation_for_movie"
    subcommand_help = "動画範囲外のアノテーションを探すためのCSVを出力します。"
    description = "動画範囲外のアノテーションを探すためのCSVを出力します。最後尾のアノテーションの開始時間、終了時間を出力します。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
