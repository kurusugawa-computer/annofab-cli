import argparse
import logging.handlers
import time
import uuid
from pathlib import Path

import pyquery

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class UploadInstruction(AbstractCommandLineInterface):
    """
    作業ガイドをアップロードする
    """

    def upload_html_to_instruction(self, project_id: str, html_path: Path):
        pq_html = pyquery.PyQuery(filename=str(html_path))
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
                img_path = html_path.parent / src_value

            if img_path.exists():
                image_id = str(uuid.uuid4())
                img_url = self.service.wrapper.upload_instruction_image(project_id, image_id, str(img_path))

                logger.debug(f"image uploaded. file={img_path}, instruction_image_url={img_url}")
                img_elm.attrib["src"] = img_url
                time.sleep(1)

            else:
                logger.warning(f"image does not exist. path={img_path}")

        # body要素があればその中身、なければhtmlファイルの中身をアップロードする
        if len(pq_html("body")) > 0:
            html_data = pq_html("body").html()
        else:
            html_data = pq_html.html()

        self.update_instruction(project_id, html_data)
        logger.info("作業ガイドを更新しました。")

    def update_instruction(self, project_id: str, html_data: str):
        histories, _ = self.service.api.get_instruction_history(project_id)
        if len(histories) > 0:
            last_updated_datetime = histories[0]["updated_datetime"]
        else:
            last_updated_datetime = None

        request_body = {"html": html_data, "last_updated_datetime": last_updated_datetime}
        self.service.api.put_instruction(project_id, request_body=request_body)

    def main(self):
        args = self.args

        self.upload_html_to_instruction(args.project_id, Path(args.html))


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UploadInstruction(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--html", type=str, required=True, help="作業ガイドとして登録するHTMLファイルのパスを指定します。body要素があればbody要素の中身をアップロードします。"
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "upload"
    subcommand_help = "HTMLファイルを作業ガイドとして登録します。"
    description = (
        "HTMLファイルを作業ガイドとして登録します。" + "img要素のsrc属性がローカルの画像を参照している場合（http, https, dataスキーマが付与されていない）、" "画像もアップロードします。"
    )
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
