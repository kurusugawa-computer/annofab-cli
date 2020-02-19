import argparse
import logging.handlers
import time
import uuid
from pathlib import Path

import pyquery

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login
from annofabcli.instruction.upload_instruction import UploadInstruction

logger = logging.getLogger(__name__)


class CopyInstruction(AbstractCommandLineInterface):
    def download_instruction(self, project_id: str) -> str:
        """project_idから作業ガイドのhtmlを取ってくるやつ"""
        history_id = self.service.api.get_instruction_history(project_id=project_id)[0][0]["history_id"]

        instruction = self.service.api.get_instruction(project_id=project_id, query_params={"history_id": history_id})[
            0
        ]["html"]

        return instruction

    def download_instruction_images(self, project_id: str):
        """project_idから作業ガイドの画像を取ってくるやつ"""
        instruction_images = self.service.api.get_instruction_images(project_id=project_id)

        # TODO:権限が無いのでこれでは取れない
        def _get_images(url):
            http_method = "GET"
            return self.service.api._request_wrapper(http_method, url)

        for instruction_image in instruction_images:
            instruction_image["image"] = _get_images(instruction_image["url"])

        return instruction_image

    def update_instruction(self, project_id: str, html: str, images):
        """画像をproject_idの作業ガイドにアップロードするやつ"""
        # TODO: urlを変更するところはまだ書いていない
        pq_html = pyquery.PyQuery(filename=str(html))
        pq_img = pq_html("img")

        # 画像をすべてアップロードして、img要素のsrc属性値を annofab urlに変更する
        for img_elm in pq_img:
            src_value: str = img_elm.attrib.get("src")
            if src_value is None:
                continue

            if src_value.startswith("http:") or src_value.startswith("https:") or src_value.startswith("data:"):
                continue

            if src_value[0] == "/":
                img_path = Path(src_value)
            else:
                img_path = html.parent / src_value

            if img_path.exists():
                image_id = str(uuid.uuid4())
                img_url = self.service.wrapper.upload_instruction_image(project_id, image_id, str(img_path))

                logger.debug(f"image uploaded. file={img_path}, instruction_image_url={img_url}")
                img_elm.attrib["src"] = img_url
                time.sleep(1)

            else:
                logger.warning(f"image does not exist. path={img_path}")

        # 作業ガイドの更新(body element)
        html_data = pq_html("body").html()
        UploadInstruction.update_instruction(project_id, html_data)
        logger.info("作業ガイドを更新しました。")

    def main(self):
        args = self.args

        # download
        instruction = self.download_instruction(args.from_id)
        instruction_images = self.download_instruction_images(args.from_id)

        # upload
        self.update_instruction(project_id=args.to_id, html=instruction, images=instruction_images)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CopyInstruction(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument("--from_id", type=str, required=True, help="作業ガイドコピー元のproject_idを指定します")
    parser.add_argument("--to_id", type=str, required=True, help="作業ガイドコピー先のproject_idを指定します")
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "copy_instruction"
    subcommand_help = "プロジェクト間で作業ガイドをコピーします"
    description = "usausa"
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
