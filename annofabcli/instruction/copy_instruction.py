import argparse
import logging
import mimetypes
from typing import Optional

import requests
from annofabapi.models import ProjectMemberRole
from pyquery import PyQuery

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login

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
        super().validate_project(
            dest_project_id, project_member_roles=[ProjectMemberRole.ACCEPTER, ProjectMemberRole.OWNER]
        )

    @staticmethod
    def get_instruction_image_id_from_url(url: str) -> str:
        # URL Queryを除いたURLを取得する
        url_without_query = url.split("?")[0]
        return url_without_query.split("/")[-1]

    @staticmethod
    def _get_mime_type_from_filename(filename: Optional[str]) -> str:
        """
        ファイル名からMIME TYPEを取得する。
        """
        DEFAULT_MIME_TYPE = "application/octet-stream"
        if filename is None:
            return DEFAULT_MIME_TYPE

        content_type = mimetypes.guess_type(filename)[0]
        return content_type if content_type is not None else DEFAULT_MIME_TYPE

    def upload_instruction_image(self, src_project_id: str, dest_project_id: str, pq_img: PyQuery) -> Optional[str]:
        """
        コピー元の作業ガイド画像を、コピー先にアップロードする。
        Args:
            src_project_id:
            dest_project_id:
            pq_img:

        Returns:
            コピー先の作業ガイドのURL。コピーできなかった場合はNoneを返す。

        """

        src_instruction_image_url: str = pq_img.attr["src"]
        if src_instruction_image_url is None:
            logger.warning(f"{pq_img} にsrc属性がないのでスキップします。")
            return None

        logger.debug(f"コピー元プロジェクトの {src_instruction_image_url} を、コピー先プロジェクトにアップロードします。")
        instruction_image_id = self.get_instruction_image_id_from_url(src_instruction_image_url)

        # alt属性値にファイル名が設定されている
        content_type = self._get_mime_type_from_filename(pq_img.attr["alt"])

        try:
            response_image = self.service.api._request_get_with_cookie(src_project_id, src_instruction_image_url)
        except requests.exceptions.RequestException as e:
            logger.warning(f"コピー元の作業ガイド画像の取得に失敗しました。: {e}")
            return None

        dest_instruction_image_url = self.service.wrapper.upload_data_as_instruction_image(
            dest_project_id, instruction_image_id, data=response_image.content, content_type=content_type
        )
        return dest_instruction_image_url

    def put_instruction(self, project_id: str, instruction_html: str) -> None:
        old_instruction = self.service.wrapper.get_latest_instruction(project_id)
        request_body = {
            "html": instruction_html,
            "last_updated_datetime": old_instruction["last_updated_datetime"] if old_instruction is not None else None,
        }
        self.service.api.put_instruction(project_id, request_body=request_body)

    def register_instruction(self, src_project_id: str, dest_project_id: str, instruction_html: str) -> None:
        """
        作業ガイド用HTMLを、作業ガイドとして登録する。
        作業ガイドHTMLに記載されている画像はダウンロードする。

        Args:
            project_id:
            instruction_html:

        Returns:

        """

        pq_html = PyQuery(instruction_html)
        pq_img_list = pq_html("img")

        for img_elm in pq_img_list:
            pq_img = PyQuery(img_elm)

            dest_instruction_image_url = self.upload_instruction_image(src_project_id, dest_project_id, pq_img)
            if dest_instruction_image_url is not None:
                pq_img.attr["src"] = dest_instruction_image_url  # pylint: disable=unsupported-assignment-operation

        self.put_instruction(dest_project_id, str(pq_html))

    def copy_instruction(self, src_project_id: str, dest_project_id: str) -> None:
        self.validate_projects(src_project_id, dest_project_id)
        src_project_title = self.facade.get_project_title(src_project_id)
        dest_project_title = self.facade.get_project_title(dest_project_id)

        src_instruction = self.service.wrapper.get_latest_instruction(src_project_id)
        if src_instruction is None:
            logger.warning(f"コピー元プロジェクト '{src_project_title}' に作業ガイドが設定されていません。終了します。")
            return

        if not self.confirm_processing(f"'{src_project_title}' の作業ガイドを、'{dest_project_title}' にコピーしますか？"):
            return

        self.register_instruction(src_project_id, dest_project_id, instruction_html=src_instruction["html"])

    def main(self) -> None:
        args = self.args

        self.copy_instruction(src_project_id=args.src_project_id, dest_project_id=args.dest_project_id)


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    CopyInstruction(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument("src_project_id", type=str, help="コピー元のプロジェクトのproject_id")
    parser.add_argument("dest_project_id", type=str, help="コピー先のプロジェクトのproject_id")
    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "copy"
    subcommand_help = "作業ガイドをコピーします。"
    description = "作業ガイドを別プロジェクトにコピーします。"
    epilog = "コピー先のプロジェクトに対して、チェッカーまたはオーナロールを持つユーザで実行してください。"
    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
