import argparse
import logging.handlers
import time
import uuid
from pathlib import Path

import pyquery
from annofabapi.models import OrganizationMember, ProjectMember, ProjectMemberRole
from annofabapi.utils import download
import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, ArgumentParser, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


class CopyInstruction(AbstractCommandLineInterface):
    """
    作業ガイドをコピーする。
    """
    def validate_projects(self, src_project_id: str, dest_project_id: str):
        """
        適切なRoleが付与されているかを確認する。

        Raises:
             AuthorizationError: 自分自身のRoleがいずれかのRoleにも合致しなければ、AuthorizationErrorが発生する。
        """
        super().validate_project(src_project_id, project_member_roles=None)
        super().validate_project(dest_project_id, project_member_roles=[ProjectMemberRole.OWNER])


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

        # 作業ガイドの更新(body element)
        html_data = pq_html("body").html()
        self.update_instruction(project_id, html_data)
        logger.info("作業ガイドを更新しました。")

    @staticmethod
    def get_instruction_image_id_from_url(url: str):
        # URL Queryを除いたURLを取得する
        url_without_query = url.split("?")[0]
        return url_without_query.split("/")[-1]



    def upload_instruction_image(self, src_instruction_image_url: str, project_id: str, temp_dir:Path):
        src_instruction_image_url
        instruction_image_id = self.get_instruction_image_id_from_url(src_instruction_image_url)

        dest_file = temp_dir / instruction_image_id

        img_url = self.service.wrapper.upload_instruction_image(project_id, image_id, str(img_path))


    def register_instruction(self, project_id: str, instruction_html: str):
        """
        作業ガイド用HTMLを、作業ガイドとして登録する。
        作業ガイドHTMLに記載されている画像はダウンロードする。

        Args:
            project_id:
            instruction_html:

        Returns:

        """

        pq_html = pyquery.PyQuery(instruction_html)
        pq_img = pq_html("img")

        # コピー画像をすべてアップロードして、img要素のsrc属性値を annofab urlに変更する
        for img_elm in pq_img:
            src_value: str = img_elm.attrib.get("src")
            if src_value is None:
                logger.warning(f"{img_elm} にsrc属性がないのでスキップします。")
                continue

            download()
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





    def copy_instruction(self, src_project_id: str, dest_project_id:str, temp_dir: Path):
        self.validate_projects(src_project_id, dest_project_id)

        instruction = self.service.wrapper.get_latest_instruction(src_project_id)
        if instruction is None:
            logger.warning(f"作業ガイドが登録されていないので、コピーしません。")
            return

        temp_dir.mkdir(parents=True, exist_ok=True)

        html =


        if len(histories) > 0:
            last_updated_datetime = histories[0]["updated_datetime"]
        else:
            last_updated_datetime = None

        request_body = {"html": html_data, "last_updated_datetime": last_updated_datetime}
        self.service.api.put_instruction(project_id, request_body=request_body)

    def main(self):
        args = self.args

        self.copy_instruction(args.project_id, Path(args.html))


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CopyInstruction(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument("src_project_id", type=str, help="コピー元のプロジェクトのproject_id")
    parser.add_argument("dest_project_id", type=str, help="コピー先のプロジェクトのproject_id")

    parser.add_argument("--temp_dir", type=str, required=True, help="temporaryディレクトリのパス。コピー元からダウンロードした作業ガイド画像を一時的に保存する。")


    parser.set_defaults(subcommand_func=main)


    argument_parser = ArgumentParser(parser)

    argument_parser.add_project_id()

    # TODO body要素内のみ？
    parser.add_argument("--html", type=str, required=True, help="作業ガイドとして登録するHTMLファイルのパスを指定します。")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "copy"
    subcommand_help = "作業ガイドをコピーします。"
    description = "作業ガイドを別プロジェクトにコピーします。"
    epilog = "コピー先のプロジェクトに対して、チェッカーまたはオーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
