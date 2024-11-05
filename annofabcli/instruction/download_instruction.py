import argparse
import logging.handlers
import sys
from pathlib import Path
from typing import Optional

import annofabapi
import pyquery

import annofabcli
from annofabcli.common.cli import (
    COMMAND_LINE_ERROR_STATUS_CODE,
    ArgumentParser,
    CommandLine,
    build_annofabapi_resource_and_login,
)
from annofabcli.common.facade import AnnofabApiFacade

logger = logging.getLogger(__name__)


class DownloadInstructionMain:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service
        self.facade = AnnofabApiFacade(service)

    def download_instruction_image(self, project_id: str, instruction_image_url: str, dest_path: Path):  # noqa: ANN201
        """
        HTTP GETで取得した内容をファイルに保存する（ダウンロードする）
        """
        response = self.service.api._request_get_with_cookie(project_id, instruction_image_url)  # noqa: SLF001
        response.raise_for_status()

        p = Path(dest_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with dest_path.open("wb") as f:
            f.write(response.content)

    def download_images(self, project_id: str, str_instruction_html: str, output_dir: Path) -> str:
        """
        すべての作業ガイド画像をダウンロードする


        Args:
            project_id:
            str_instruction_html:
            output_dir:

        Returns:
            ローカルの作業ガイド画像が記載されたHTMLを返す。
        """
        pq = pyquery.PyQuery(str_instruction_html)
        pq_img = pq("img")

        # img要素のsrc属性値が作業ガイド画像（先頭が`https://annofab.com/projects/{project_id}/instruction-images/`）の場合は
        # 画像をすべてダウンロードして、img要素のsrc属性値をローカルのファイルを参照するように変更する
        src_value_prefix = f"https://annofab.com/projects/{project_id}/instruction-images/"

        def _get_instruction_image_id(image_url: str) -> str:
            return image_url[len(src_value_prefix) : image_url.index("?")]

        img_dir = output_dir / "img"
        img_dir.mkdir(exist_ok=True, parents=True)
        for img_elm in pq_img:
            src_value: Optional[str] = img_elm.attrib.get("src")
            if src_value is None:
                continue

            if not src_value.startswith(src_value_prefix):
                continue

            try:
                instruction_image_id = _get_instruction_image_id(src_value)
                img_output_path = img_dir / instruction_image_id
                self.download_instruction_image(project_id, src_value, img_output_path)
                logger.debug(f"{src_value} を {img_output_path} にダウンロードしました。")
                img_elm.attrib["src"] = f"img/{instruction_image_id}"
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(e)
                logger.warning(f"{src_value} のダウンロードに失敗しました。")

        return pq.outer_html()

    def download_instruction(self, project_id: str, output_dir: Path, history_id: Optional[str] = None, is_download_image: bool = False):  # noqa: ANN201, FBT001, FBT002
        """
        作業ガイドをダウンロードする

        Args:
            project_id:
            output_dir:
            history_id: Noneの場合は最新の作業ガイドを取得する。

        Returns:

        """
        if history_id is None:
            content = self.service.wrapper.get_latest_instruction(project_id)
            if content is None:
                logger.warning(f"project_id={project_id} のプロジェクトに作業ガイドは設定されていなかったので、ダウンロードできませんでした。")
                return
            str_instruction_html = content["html"]
        else:
            content2, _ = self.service.api.get_instruction(project_id, query_params={"history_id": history_id})
            str_instruction_html = content2["html"]

        output_dir.mkdir(exist_ok=True, parents=True)
        if is_download_image:
            str_instruction_html = self.download_images(project_id, str_instruction_html=str_instruction_html, output_dir=output_dir)

        output_html = output_dir / "index.html"
        output_html.write_text(str_instruction_html, encoding="utf-8")
        logger.debug(f"{output_html} をダウンロードしました。")


class DownloadInstruction(CommandLine):
    COMMON_MESSAGE = "annofabcli instruction download"

    def get_history_id_from_before_index(self, project_id: str, before: int) -> Optional[str]:
        histories, _ = self.service.api.get_instruction_history(project_id, query_params={"limit": 10000})
        if before + 1 > len(histories):
            logger.warning(f"作業ガイドの変更履歴は{len(histories)}個のため、最新より{before}個前の作業ガイドは見つかりませんでした。")
            return None

        history = histories[before]
        return history["history_id"]

    def main(self) -> None:
        args = self.args

        project_id = args.project_id
        super().validate_project(project_id)

        if args.before is not None:
            history_id = self.get_history_id_from_before_index(args.project_id, args.before)
            if history_id is None:
                print(  # noqa: T201
                    f"{self.COMMON_MESSAGE} argument --before: 最新より{args.before}個前のアノテーション仕様は見つかりませんでした。",
                    file=sys.stderr,
                )
                sys.exit(COMMAND_LINE_ERROR_STATUS_CODE)
        else:
            history_id = args.history_id

        main_obj = DownloadInstructionMain(self.service)
        main_obj.download_instruction(project_id, output_dir=args.output_dir, history_id=history_id, is_download_image=args.download_image)


def main(args: argparse.Namespace) -> None:
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    DownloadInstruction(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser) -> None:
    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    # 過去の作業ガイドを参照するためのオプション
    old_instruction_group = parser.add_mutually_exclusive_group()

    old_instruction_group.add_argument(
        "--history_id",
        type=str,
        help=(
            "ダウンロードしたい作業ガイドのhistory_idを指定してください。 "
            "history_idは`$ annofabcli instruction list_history`コマンドで確認できます。 "
            "指定しない場合は、最新の作業ガイドが出力されます。 "
        ),
    )

    old_instruction_group.add_argument(
        "--before",
        type=int,
        help=(
            "ダウンロードしたい作業ガイドが、最新版よりいくつ前の作業ガイドであるかを指定してください。  "
            "たとえば`1`を指定した場合、最新より1個前の作業ガイドをダウンロードします。 "
            "指定しない場合は、最新の作業ガイドをダウンロードします。 "
        ),
    )

    parser.add_argument(
        "--download_image",
        action="store_true",
        help="作業ガイド画像もダウンロードします。指定した場合、img要素のsrc属性はローカルのファイルを参照するようになります。",
    )

    parser.add_argument("-o", "--output_dir", type=Path, required=True, help="出力先ディレクトリのパスを指定してください。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: Optional[argparse._SubParsersAction] = None) -> argparse.ArgumentParser:
    subcommand_name = "download"
    subcommand_help = "作業ガイドをダウンロードします。"
    description = "作業ガイドをダウンロードします。HTMLファイルにはbodyタグの内部が記載されています。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
    return parser
