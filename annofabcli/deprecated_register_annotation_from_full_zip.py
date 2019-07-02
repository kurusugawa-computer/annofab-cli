"""
ラスタ画像をアノテーションとして登録する
"""

import argparse
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional  # pylint: disable=unused-import

import annofabapi
import annofabcli
import PIL
import PIL.Image
import PIL.ImageDraw
from annofabapi.typing import Annotation
from annofabcli import AnnofabApiFacade
from annofabcli.common.typing import InputDataSize
from annofabcli.common.utils import build_annofabapi_resource_and_login


logger = logging.getLogger(__name__)

FilterDetailsFunc = Callable[[Annotation], bool]
"""アノテーションをFilterする関数"""


class RegisterAnnotation:
    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade):
        self.service = service
        self.facade = facade

    # AnnofabAPI をカスタマイズ
    def get_annotations_for_editor(self, project_id: str, task_id: str, input_data_id: str):
        url_path = f'/projects/{project_id}/tasks/{task_id}/inputs/{input_data_id}/annotation'
        http_method = 'GET'
        keyword_params: Dict[str, Any] = {}
        return self.service.api._request_wrapper(http_method, url_path, **keyword_params)

    @staticmethod
    def draw_annotation_list(annotation_list: List[Annotation], draw: PIL.ImageDraw.Draw) -> PIL.ImageDraw.Draw:
        """
        矩形、ポリゴンを描画する。
        Args:
            annotation_list: アノテーション List
            draw: (IN/OUT) PillowのDrawing Object. 変更される。
        Returns:
            描画したPillowのDrawing Object

        """
        for annotation in annotation_list:
            data = annotation["data"]
            color = (255, 255, 255, 255)
            data_type = data["_type"]
            if data_type == "BoundingBox":
                xy = [(data["left_top"]["x"], data["left_top"]["y"]),
                      (data["right_bottom"]["x"], data["right_bottom"]["y"])]
                draw.rectangle(xy, fill=color)

            elif data_type == "Points":
                # Polygon
                xy = [(e["x"], e["y"]) for e in data["points"]]
                draw.polygon(xy, fill=color)

            # elif data_type == "SegmentationV2":
            #     # polygonを塗りつぶしに変換してしまったから対応する場合
            #     xy = [float(e) for e in data["data_uri"].split(",")]
            #     draw.polygon(xy, fill=color)

        return draw

    def update_annotation_with_image(self, project_id: str, task_id: str, input_data_id: str,
                                     image_file_list: List[Any], account_id: str, filter_details: FilterDetailsFunc):
        """
        塗りつぶしアノテーションを登録する。他のアノテーションが変更されないようにする。
        アノテーションを登録できる状態であること

        Args:
            project_id:
            task_id:
            input_data_id:
            image_file_list:
            account_id:
            filter_details: 残すアノテーションの条件。Trueを返せば残す、Falseのときは削除

        Returns:

        """

        old_annotations = self.get_annotations_for_editor(project_id, task_id, input_data_id)[0]
        old_details = old_annotations["details"]

        details = [e for e in old_details if filter_details(e)]
        for detail in details:
            detail.pop("etag", None)
            detail.pop("url", None)

        for e in image_file_list:
            image_file = e["path"]
            label_id = e["label_id"]

            s3_path = self.service.wrapper.upload_file_to_s3(project_id, image_file, "image/png")
            annotation_id = str(uuid.uuid4())

            detail = {
                "account_id": account_id,
                "additional_data_list": [],
                "annotation_id": annotation_id,
                "created_datetime": None,
                "data": None,
                "data_holding_type": "outer",
                "etag": None,
                "is_protected": False,
                "label_id": label_id,
                "path": s3_path,
                "updated_datetime": None,
                "url": None,
            }

            details.append(detail)

        request_body = {
            "project_id": project_id,
            "task_id": task_id,
            "input_data_id": input_data_id,
            "details": details,
            "updated_datetime": old_annotations["updated_datetime"]
        }

        return self.service.api.put_annotation(project_id, task_id, input_data_id, request_body=request_body)[0]

    def write_segmentation_image(self, input_data: Dict[str, Any], label: str, label_id: str, tmp_image_path: Path,
                                 input_data_size: InputDataSize):

        image = PIL.Image.new(mode="RGBA", size=input_data_size, color=(0, 0, 0, 0))
        draw = PIL.ImageDraw.Draw(image)

        # labelで絞り込み
        annotation_list = [e for e in input_data["detail"] if e["label_id"] == label_id]
        if len(annotation_list) == 0:
            logger.info(
                f"{input_data['task_id']}, {input_data['input_data_id']} に label:{label}, label_id:{label_id} のアノテーションがない"
            )
            return False

        # アノテーションを描画する
        self.draw_annotation_list(annotation_list, draw)

        tmp_image_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(str(tmp_image_path))
        logger.info(f"{str(tmp_image_path)} の生成完了")
        return True

    def write_segmentation_image_for_labels(self, labels: List[Dict[str, str]], input_data: Dict[str, Any],
                                            default_input_data_size: InputDataSize, tmp_image_dir: Path):
        """
        ラベルごとに、セマンティック画像ファイルを出力する。
        Args:
            labels:
            input_data:
            default_input_data_size:
            tmp_image_dir:

        Returns:

        """

        image_file_list = []
        for label_dict in labels:
            label = label_dict["label"]
            label_id = label_dict["label_id"]

            tmp_image_path = tmp_image_dir / f"{label}.png"

            result = self.write_segmentation_image(input_data=input_data, label=label, label_id=label_id,
                                                   tmp_image_path=tmp_image_path,
                                                   input_data_size=default_input_data_size)

            if result:
                image_file_list.append({"path": str(tmp_image_path), "label_id": label_id})

        return image_file_list

    def register_raster_annotation_from_polygon(self, annotation_dir: str, default_input_data_size: InputDataSize,
                                                tmp_dir: str, labels: List[Dict[str, str]], project_id: str,
                                                task_id_list: List[str], filter_details: FilterDetailsFunc):
        annotation_dir_path = Path(annotation_dir)
        tmp_dir_path = Path(tmp_dir)

        tmp_dir_path.mkdir(exist_ok=True)

        account_id = self.facade.get_my_account_id()

        for task_id in task_id_list:
            task_dir = annotation_dir_path / task_id

            for input_data_json_path in task_dir.iterdir():
                if not input_data_json_path.is_file():
                    continue

                with open(str(input_data_json_path)) as f:
                    input_data = json.load(f)

                input_data_id = input_data["input_data_id"]

                tmp_image_dir = tmp_dir_path / task_dir.name / input_data_json_path.stem
                try:
                    image_file_list = self.write_segmentation_image_for_labels(labels, input_data,
                                                                               default_input_data_size, tmp_image_dir)

                except Exception as e:
                    logger.exception(e)
                    logger.warning(f"{task_id}, {input_data_id}, {str(tmp_image_dir)} 用のセグメンテーション画像の生成失敗")
                    continue

                if len(image_file_list) == 0:
                    continue

                try:
                    # annotaion phase or acceptance phaseであること
                    task = self.service.api.get_task(project_id, task_id)[0]
                    if task["account_id"] == account_id and task["status"] == "working":
                        logger.info(f"{task_id} {input_data_id} 自分自身に割り合っていて、作業中のため、担当者を変更しない")
                    else:
                        self.facade.change_operator_of_task(project_id, task_id, account_id)
                        self.facade.change_to_working_phase(project_id, task_id, account_id)
                except Exception as e:
                    logger.warning(e)
                    logger.warning(f"{task_id}, {input_data_id} の担当者変更 or 作業中に変更に失敗")
                    continue

                try:
                    # アノテーションの登録
                    self.update_annotation_with_image(project_id, task_id, input_data_id, account_id=account_id,
                                                      image_file_list=image_file_list, filter_details=filter_details)

                    self.facade.change_to_break_phase(project_id, task_id, account_id)

                    logger.info(f"{task_id}, {input_data_id} アノテーションの登録完了")

                except Exception as e:
                    logger.warning(e)
                    logger.warning(f"{task_id}, {input_data_id} のアノテーション登録失敗")

    def main(self, args):
        """
        main処理。
        注意：このメソッドを修正すること
        """

        annofabcli.utils.load_logging_config_from_args(args, __file__)

        logger.info(f"args: {args}")

        try:
            default_input_data_size = annofabcli.utils.get_input_data_size(args.input_data_size)

        except Exception as e:
            logger.error("--default_input_data_size のフォーマットが不正です")
            raise e

        def filter_details(annotation: Annotation) -> bool:
            """
            残すアノテーションの条件
            Args:
                annotation:

            Returns:

            """
            exclude_label_ids = [
                "030bc859-4933-4bec-baa0-18fc80fb1eea",  #vehicle
                "4bc53fa5-bb2e-44a5-adb2-04c76d87bfde"  # motorcycle
            ]
            label_id = annotation["label_id"]
            # 除外するlabel_idにマッチしたらFalse
            return label_id not in exclude_label_ids

        labels = [{
            "label": "vehicle",
            "label_id": "030bc859-4933-4bec-baa0-18fc80fb1eea"
        }, {
            "label": "motorcycle",
            "label_id": "4bc53fa5-bb2e-44a5-adb2-04c76d87bfde"
        }]

        task_id_list = annofabcli.utils.read_lines_except_blank_line(args.task_id_file)

        self.register_raster_annotation_from_polygon(annotation_dir=args.annotation_dir,
                                                     default_input_data_size=default_input_data_size,
                                                     tmp_dir=args.tmp_dir, labels=labels, project_id=args.project_id,
                                                     filter_details=filter_details, task_id_list=task_id_list)


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument('--annotation_dir', type=str, required=True, help='アノテーションFull zipを展開したディレクトリのパス')

    parser.add_argument('--input_data_size', type=str, required=True, help='入力データ画像のサイズ。{width}x{height}。ex. 1280x720')

    parser.add_argument('--tmp_dir', type=str, required=True, help='temporaryディレクトリのパス')

    parser.add_argument('--project_id', type=str, required=True, help='塗りつぶしv2アノテーションを登録するプロジェクトのproject_id')

    parser.add_argument('--task_id_file', type=str, required=True, help='task_idの一覧が記載されたファイル')


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    RegisterAnnotation(service, facade).main(args)


if __name__ == "__main__":
    global_parser = argparse.ArgumentParser(
        description="deprecated: 矩形/ポリゴンアノテーションを、塗りつぶしv2アノテーションとして登録する。"
        "注意：対象プロジェクトに合わせてスクリプトを修正すること。そのままでは実行できに。", parents=[annofabcli.utils.create_parent_parser()])

    parse_args(global_parser)

    try:
        main(global_parser.parse_args())
    except Exception as e:
        logger.exception(e)
        raise e
