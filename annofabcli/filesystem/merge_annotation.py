import argparse
import json
import logging
import sys
import zipfile
from collections.abc import Collection, Iterator
from pathlib import Path
from typing import Any, Callable, Optional

from annofabapi.parser import (
    SimpleAnnotationDirParser,
    SimpleAnnotationParser,
    SimpleAnnotationZipParser,
    lazy_parse_simple_annotation_dir,
    lazy_parse_simple_annotation_zip,
)

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLineWithoutWebapi,
    get_list_from_args,
)

IsParserFunc = Callable[[SimpleAnnotationParser], bool]


logger = logging.getLogger(__name__)


class MergeAnnotationMain:
    @staticmethod
    def create_iter_parser(annotation_path: Path) -> Iterator[SimpleAnnotationParser]:
        # Simpleアノテーションの読み込み
        if annotation_path.is_file():
            return lazy_parse_simple_annotation_zip(annotation_path)
        elif annotation_path.is_dir():
            return lazy_parse_simple_annotation_dir(annotation_path)
        else:
            raise RuntimeError(f"{annotation_path} はサポート対象外です。")

    @staticmethod
    def _write_outer_file(parser: SimpleAnnotationParser, anno: dict[str, Any], output_json: Path) -> None:
        data_uri = anno["data"]["data_uri"]

        with parser.open_outer_file(data_uri) as src_f:
            data = src_f.read()
            output_outer_file = output_json.parent / f"{output_json.stem}/{data_uri}"
            output_outer_file.parent.mkdir(parents=True, exist_ok=True)
            with output_outer_file.open("wb") as dest_f:
                dest_f.write(data)

    @staticmethod
    def _is_segmentation(anno: dict[str, Any]) -> bool:
        return anno["data"]["_type"] in ["Segmentation", "SegmentationV2"]

    def write_merged_annotation(self, parser1: SimpleAnnotationParser, parser2: SimpleAnnotationParser, output_json: Path):  # noqa: ANN201
        simple_annotation1 = parser1.load_json()
        simple_annotation2 = parser2.load_json()
        details1 = simple_annotation1["details"]
        details2 = simple_annotation2["details"]

        # dictのキーの順序が保証されていること前提
        details2_dict = {e["annotation_id"]: e for e in details2}

        merged_details = []
        for anno1 in details1:
            annotation_id = anno1["annotation_id"]
            anno2 = details2_dict.get(annotation_id)
            if anno2 is not None:
                del details2_dict[annotation_id]
                new_anno = anno2
                adopt_two = True
            else:
                new_anno = anno1
                adopt_two = False

            merged_details.append(new_anno)
            # 塗りつぶしアノテーションファイルをコピーする
            if self._is_segmentation(new_anno):
                self._write_outer_file(parser=(parser2 if adopt_two else parser1), anno=new_anno, output_json=output_json)

        merged_details.extend(list(details2_dict.values()))

        # マージ後でも意味のある情報のみ残す
        new_simple_annotation = {
            "task_id": simple_annotation1["task_id"],
            "input_data_id": simple_annotation1["input_data_id"],
            # input_data_idが一致しているなら、input_data_nameも同じであるという前提
            "input_data_name": simple_annotation1["input_data_name"],
            "details": merged_details,
        }

        output_json.parent.mkdir(parents=True, exist_ok=True)
        with output_json.open("w", encoding="utf-8") as f:
            json.dump(new_simple_annotation, f, ensure_ascii=False)

    def copy_annotation(self, parser: SimpleAnnotationParser, output_json: Path):  # noqa: ANN201
        simple_annotation = parser.load_json()
        details = simple_annotation["details"]

        for anno in details:
            # 塗りつぶしアノテーションファイルをコピーする
            if self._is_segmentation(anno):
                self._write_outer_file(parser, anno, output_json)

        output_json.parent.mkdir(exist_ok=True, parents=True)
        with output_json.open("w", encoding="utf-8") as f:
            json.dump(simple_annotation, f, ensure_ascii=False)

    @staticmethod
    def _get_parser(annotation_path: Path, zip_file: Optional[zipfile.ZipFile], json_path: Path) -> Optional[SimpleAnnotationParser]:
        if annotation_path.is_dir():
            if (annotation_path / json_path).exists():
                return SimpleAnnotationDirParser(annotation_path / json_path)
            else:
                return None
        elif annotation_path.is_file() and zip_file is not None:
            # zipファイルであるという前提
            if str(json_path) in zip_file.namelist():
                return SimpleAnnotationZipParser(zip_file, str(json_path))
            return None
        else:
            raise RuntimeError(f"{annotation_path} はサポート対象外です。")

    @staticmethod
    def create_is_target_parser_func(
        task_ids: Optional[Collection[str]] = None,
    ) -> Optional[IsParserFunc]:
        if task_ids is None:
            return None

        task_id_set = set(task_ids) if task_ids is not None else None

        def is_target_parser(parser: SimpleAnnotationParser) -> bool:
            if task_id_set is not None and len(task_id_set) > 0:  # noqa: SIM102
                if parser.task_id not in task_id_set:
                    return False

            return True

        return is_target_parser

    def main(  # noqa: ANN201
        self,
        annotation_path1: Path,
        annotation_path2: Path,
        output_dir: Path,
        target_task_ids: Optional[Collection[str]] = None,
    ):
        is_target_parser_func = self.create_is_target_parser_func(target_task_ids)

        iter_parser1 = self.create_iter_parser(annotation_path1)

        zip_file2: Optional[zipfile.ZipFile] = None
        if annotation_path2.is_file():
            zip_file2 = zipfile.ZipFile(str(annotation_path2), "r")  # pylint: disable=consider-using-with

        excluded_json_path2: set[str] = set()
        for parser1 in iter_parser1:
            if is_target_parser_func is not None and not is_target_parser_func(parser1):
                continue

            json_file1 = Path(parser1.json_file_path)
            json_file_path1 = f"{json_file1.parent.name}/{json_file1.name}"
            output_json = output_dir / json_file_path1

            parser2 = self._get_parser(annotation_path2, zip_file=zip_file2, json_path=Path(json_file_path1))
            if parser2 is not None:
                # annotation_path1とannotation_path2両方に存在するJSONをマージして出力する
                self.write_merged_annotation(parser1, parser2, output_json)
                excluded_json_path2.add(json_file_path1)
            else:
                # annotation_path2に存在しないJSONを出力する
                self.copy_annotation(parser1, output_json)
            logger.debug(f"{output_json} を出力しました。")

        if zip_file2 is not None:
            zip_file2.close()

        # annotation_path1に存在しないJSONを出力する
        iter_parser2 = self.create_iter_parser(annotation_path2)
        for parser2 in iter_parser2:
            if is_target_parser_func is not None and not is_target_parser_func(parser2):
                continue
            json_file2 = Path(parser2.json_file_path)
            json_file_path2 = f"{json_file2.parent.name}/{json_file2.name}"
            if json_file_path2 in excluded_json_path2:
                continue

            output_json = output_dir / json_file_path2
            self.copy_annotation(parser2, output_json)
            logger.debug(f"{output_json} を出力しました。")


class MergeAnnotation(CommandLineWithoutWebapi):
    @staticmethod
    def validate(args: argparse.Namespace) -> bool:
        COMMON_MESSAGE = "annofabcli filesystem merge_annotation: error:"  # noqa: N806
        if args.annotation is not None:
            annotation_paths: list[Path] = args.annotation
            for path in annotation_paths:
                if not path.exists():
                    print(  # noqa: T201
                        f"{COMMON_MESSAGE} argument --annotation: ファイルパス '{path}' が存在しません。",
                        file=sys.stderr,
                    )
                    return False
        return True

    def main(self) -> None:
        args = self.args
        if not self.validate(args):
            sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)

        main_obj = MergeAnnotationMain()
        target_task_ids = get_list_from_args(args.task_id) if args.task_id is not None else None
        main_obj.main(args.annotation[0], args.annotation[1], output_dir=args.output_dir, target_task_ids=target_task_ids)


def main(args: argparse.Namespace) -> None:
    MergeAnnotation(args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    parser.add_argument(
        "--annotation",
        type=Path,
        nargs=2,
        required=True,
        help="Annofabからダウンロードしたアノテーションzip、またはzipを展開したディレクトリを2つ指定してください。",
    )

    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリ")

    argument_parser.add_task_id(
        required=False,
        help_message=("マージ対象であるタスクのtask_idを指定します。指定しない場合、すべてのタスクがマージ対象です。 ``file://`` を先頭に付けると、task_idの一覧が記載されたファイルを指定できます。"),
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "merge_annotation"

    subcommand_help = "2つのアノテーションzip（またはzipを展開したディレクトリ）をマージします。"

    description = "2つのアノテーションzip（またはzipを展開したディレクトリ）をマージします。具体的にはアノテーションjsonの'details'キー配下の情報をマージします。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
