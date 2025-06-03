from __future__ import annotations

import argparse
import hashlib
import io
import logging.handlers
import tempfile
import uuid
from pathlib import Path
from typing import Optional

import pyquery
from datauri import DataURI
from PIL import Image

import annofabcli
from annofabcli.common.cli import ArgumentParser, CommandLine, build_annofabapi_resource_and_login
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


def save_image_from_data_uri_scheme(value: str, temp_dir: Path) -> Path:
    """Data URI Schemeの値を画像として保存します。

    Args:
        value (str): Data URI Schemeの値
        temp_dir (Path): 保存先ディレクトリ

    Returns:
        Path: 保存した画像パス
    """
    uri = DataURI(value)
    mimetype = uri.mimetype
    assert mimetype is not None
    # "image/png"というmimetypeから"png"を取り出して、それをファイルの拡張子とする
    extension = mimetype.split("/")[1]

    md5_hash = hashlib.md5(uri.data).hexdigest()
    image_file_name = f"{md5_hash}.{extension}"

    with Image.open(io.BytesIO(uri.data)) as img:
        image_file_path = temp_dir / image_file_name
        img.save(str(image_file_path), extension.upper())
        logger.debug(f"Data URI Schemeの画像を {image_file_path!s} に保存しました。")
        return image_file_path


class UploadInstruction(CommandLine):
    """
    作業ガイドをアップロードする
    """

    def upload_html_to_instruction(self, project_id: str, html_path: Path, temp_dir: Path) -> None:  # noqa: PLR0912
        with html_path.open(encoding="utf-8") as f:
            file_content = f.read()
        pq_html = pyquery.PyQuery(file_content)
        pq_img = pq_html("img")

        img_path_dict: dict[str, str] = {}
        # 画像をすべてアップロードして、img要素のsrc属性値を annofab urlに変更する
        for img_elm in pq_img:
            src_value: Optional[str] = img_elm.attrib.get("src")
            if src_value is None:
                continue

            if src_value.startswith(("http:", "https:")):
                continue

            if src_value.startswith("data:"):
                img_path = save_image_from_data_uri_scheme(src_value, temp_dir=temp_dir)
            else:  # noqa: PLR5501
                if src_value[0] == "/":
                    img_path = Path(src_value)
                else:
                    img_path = html_path.parent / src_value

            if str(img_path) in img_path_dict:
                image_id = img_path_dict[str(img_path)]
                img_url = f"https://annofab.com/projects/{project_id}/instruction-images/{image_id}"
                img_elm.attrib["src"] = img_url
                continue

            if img_path.exists():
                image_id = str(uuid.uuid4())

                try:
                    img_url = self.service.wrapper.upload_instruction_image(project_id, image_id, str(img_path))
                    logger.debug(f"image uploaded. file={img_path}, instruction_image_url={img_url}")
                    img_elm.attrib["src"] = img_url
                    img_path_dict[str(img_path)] = image_id
                except Exception as e:  # pylint: disable=broad-except
                    logger.warning(f"作業ガイドの画像登録に失敗しました。image_id={image_id}, img_path={img_path}, {e}")
                    continue

            else:
                logger.warning(f"image does not exist. path={img_path}")
                continue

        # body要素があればその中身、なければhtmlファイルの中身をアップロードする
        if len(pq_html("body")) > 0:
            html_data = pq_html("body").html()
        else:
            html_data = pq_html.html()

        self.update_instruction(project_id, html_data)
        logger.info("作業ガイドを更新しました。")

    def update_instruction(self, project_id: str, html_data: str) -> None:
        histories, _ = self.service.api.get_instruction_history(project_id)
        if len(histories) > 0:
            last_updated_datetime = histories[0]["updated_datetime"]
        else:
            last_updated_datetime = None

        request_body = {"html": html_data, "last_updated_datetime": last_updated_datetime}
        self.service.api.put_instruction(project_id, request_body=request_body)

    def main(self) -> None:
        args = self.args

        with tempfile.TemporaryDirectory() as str_temp_dir:
            self.upload_html_to_instruction(args.project_id, Path(args.html), temp_dir=Path(str_temp_dir))


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    UploadInstruction(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    parser.add_argument(
        "--html",
        type=str,
        required=True,
        help="作業ガイドとして登録するHTMLファイルのパスを指定します。body要素があればbody要素の中身をアップロードします。",
    )

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "upload"
    subcommand_help = "HTMLファイルを作業ガイドとして登録します。"
    description = "HTMLファイルを作業ガイドとして登録します。img要素のsrc属性がローカルの画像を参照している場合（http, https, dataスキーマが付与されていない）、画像もアップロードします。"
    epilog = "チェッカーまたはオーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
    return parser
