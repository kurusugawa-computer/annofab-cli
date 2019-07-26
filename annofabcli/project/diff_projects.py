"""
プロジェクト間の差分を表示する。
"""

import argparse
import copy
import logging
import pprint
from typing import Any, Dict, List  # pylint: disable=unused-import

import annofabapi
import dictdiffer
import more_itertools
from annofabapi.models import ProjectMemberRole

import annofabcli
import annofabcli.common.cli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login

logger = logging.getLogger(__name__)


def sorted_inspection_phrases(phrases: List[Dict[str, Any]]):
    return sorted(phrases, key=lambda e: e["id"])


def sorted_project_members(project_members: List[Dict[str, Any]]):
    return sorted(project_members, key=lambda e: e["user_id"])


def create_ignored_label(label: Dict[str, Any]):
    """
    比較対象外のkeyを削除したラベル情報を生成する
    """

    copied_label = copy.deepcopy(label)
    copied_label.pop("label_id", None)

    additional_data_definitions = copied_label["additional_data_definitions"]
    for additional_data in additional_data_definitions:
        additional_data.pop("additional_data_definition_id", None)
        choices = additional_data["choices"]
        for choice in choices:
            choice.pop("choice_id", None)

    return copied_label


class DiffProjecs(AbstractCommandLineInterface):
    """
    プロジェクト間の差分を表示する
    """
    def __init__(self, service: annofabapi.Resource, facade: AnnofabApiFacade, args: argparse.Namespace):
        super().__init__(service, facade, args)

        project_id1 = args.project_id1
        project_id2 = args.project_id2
        project_title1 = self.facade.get_project_title(project_id1)
        project_title2 = self.facade.get_project_title(project_id2)

        self.project_title1 = project_title1
        self.project_title2 = project_title2

    def diff_project_members(self, project_id1: str, project_id2: str):
        """
        プロジェクト間のプロジェクトメンバの差分を表示する。
        Args:
            project_id1: 比較対象のプロジェクトのproject_id
            project_id2: 比較対象のプロジェクトのproject_id

        Returns:
            差分があれば Trueを返す

        """
        logger.info("=== プロジェクトメンバの差分 ===")

        project_members1 = self.service.wrapper.get_all_project_members(project_id1)
        project_members2 = self.service.wrapper.get_all_project_members(project_id2)

        # プロジェクトメンバは順番に意味がないので、ソートしたリストを比較する
        sorted_members1 = sorted_project_members(project_members1)
        sorted_members2 = sorted_project_members(project_members2)

        user_ids1 = [e["user_id"] for e in sorted_members1]
        user_ids2 = [e["user_id"] for e in sorted_members2]

        if user_ids1 != user_ids2:
            print("user_idのListに差分あり")
            print(f"set(user_ids1) - set(user_ids2) = {set(user_ids1) - set(user_ids2)}")
            print(f"set(user_ids2) - set(user_ids1) = {set(user_ids2) - set(user_ids1)}")
            return True

        is_different = False
        for member1, member2 in zip(sorted_members1, sorted_members2):
            ignored_key = {"updated_datetime", "created_datetime", "project_id"}
            diff_result = list(dictdiffer.diff(member1, member2, ignore=ignored_key))
            if len(diff_result) > 0:
                is_different = True
                print(f"差分のあるuser_id: {member1['user_id']}")
                pprint.pprint(diff_result)

        if not is_different:
            logger.info("プロジェクトメンバは同じ")

        return is_different

    def is_duplicated(self, label_names1: List[str], label_names2: List[str]) -> bool:
        """
        label_nameが重複しているか確認する
        Args:
            label_names1:
            label_names2:

        Returns:
            Trueなら、label_names1 or label_names2が重複している

        """
        duplicated_set1 = annofabcli.utils.duplicated_set(label_names1)
        duplicated_set2 = annofabcli.utils.duplicated_set(label_names2)

        flag = False
        if len(duplicated_set1) > 0:
            print(f"{self.project_title1}のラベル名(en)が重複しています。{duplicated_set1}")
            flag = True

        if len(duplicated_set2) > 0:
            print(f"{self.project_title2}のラベル名(en)が重複しています。{duplicated_set2}")
            flag = True

        return flag

    def diff_labels_of_annotation_specs(self, labels1: List[Dict[str, Any]], labels2: List[Dict[str, Any]]) -> bool:
        """
        アノテーションラベル情報の差分を表示する。ラベル名(英語)を基準に差分を表示する。
        以下の項目は無視して比較する。
         * label_id
         * additional_data_definition_id
         * choice_id
        Args:
            labels1: 比較対象のラベル情報
            labels2: 比較対象のラベル情報

        Returns:
            差分があれば Trueを返す
        """
        logger.info("=== アノテーションラベル情報の差分 ===")

        label_names1 = [AnnofabApiFacade.get_label_name_en(e) for e in labels1]
        label_names2 = [AnnofabApiFacade.get_label_name_en(e) for e in labels2]

        # 重複チェック
        if self.is_duplicated(label_names1, label_names2):
            print("ラベル名(en)が重複しているので、アノテーションラベル情報の差分は確認しません。")

        if label_names1 != label_names2:
            print("ラベル名(en)のListに差分あり")
            print(f"label_names1: {label_names1}")
            print(f"label_names2: {label_names2}")
            # 両方に存在するlabel_nameのみ確認する
            is_different = True
            label_names = list(set(label_names1) & set(label_names2))
        else:
            is_different = False
            label_names = label_names1

        for label_name in label_names:

            def get_label_func(x):
                return AnnofabApiFacade.get_label_name_en(x) == label_name  # pylint: disable=cell-var-from-loop

            label1 = more_itertools.first_true(labels1, pred=get_label_func)
            label2 = more_itertools.first_true(labels2, pred=get_label_func)

            diff_result = list(dictdiffer.diff(create_ignored_label(label1), create_ignored_label(label2)))
            if len(diff_result) > 0:
                is_different = True
                print(f"ラベル名(en): {label_name} は差分あり")
                pprint.pprint(diff_result)
            else:
                logger.debug(f"ラベル名(en): {label_name} は同じ")

        if not is_different:
            logger.info("アノテーションラベルは同じ")

        return is_different

    @staticmethod
    def diff_inspection_phrases(inspection_phrases1: List[Dict[str, Any]],
                                inspection_phrases2: List[Dict[str, Any]]) -> bool:
        """
        定型指摘の差分を表示する。定型指摘IDを基準に差分を表示する。

        Args:
            inspection_phrases1: 比較対象の定型指摘List
            inspection_phrases2: 比較対象の定型指摘List

        Returns:
            差分があれば Trueを返す

        """
        logger.info("=== 定型指摘の差分 ===")

        # 定型指摘は順番に意味がないので、ソートしたリストを比較する
        sorted_inspection_phrases1 = sorted_inspection_phrases(inspection_phrases1)
        sorted_inspection_phrases2 = sorted_inspection_phrases(inspection_phrases2)

        phrase_ids1 = [e["id"] for e in sorted_inspection_phrases1]
        phrase_ids2 = [e["id"] for e in sorted_inspection_phrases2]

        if phrase_ids1 != phrase_ids2:
            print("定型指摘IDのListに差分あり")
            print(f"set(phrase_ids1) - set(phrase_ids2) = {set(phrase_ids1) - set(phrase_ids2)}")
            print(f"set(phrase_ids2) - set(phrase_ids1) = {set(phrase_ids2) - set(phrase_ids1)}")
            return True

        is_different = False
        for phrase1, phrase2 in zip(sorted_inspection_phrases1, sorted_inspection_phrases2):
            diff_result = list(dictdiffer.diff(phrase1, phrase2))
            if len(diff_result) > 0:
                is_different = True
                print(f"定型指摘に: {phrase1['id']} は差分あり")
                pprint.pprint(diff_result)

        if not is_different:
            logger.info("定型指摘は同じ")

        return is_different

    def diff_annotation_specs(self, project_id1: str, project_id2: str, diff_targets: List[str]):
        """
        プロジェクト間のアノテーション仕様の差分を表示する。
        Args:
            project_id1: 比較対象のプロジェクトのproject_id
            project_id2: 比較対象のプロジェクトのproject_id
            diff_targets: 比較対象の項目

        """

        annotation_specs1, _ = self.service.api.get_annotation_specs(project_id1)
        annotation_specs2, _ = self.service.api.get_annotation_specs(project_id2)

        if "inspection_phrases" in diff_targets:
            self.diff_inspection_phrases(annotation_specs1["inspection_phrases"],
                                         annotation_specs2["inspection_phrases"])

        if "annotation_labels" in diff_targets:
            self.diff_labels_of_annotation_specs(annotation_specs1["labels"], annotation_specs2["labels"])

    def diff_project_settingss(self, project_id1: str, project_id2: str):
        """
        プロジェクト間のプロジェクト設定の差分を表示する。
        Args:
            project_id1: 比較対象のプロジェクトのproject_id
            project_id2: 比較対象のプロジェクトのproject_id


        Returns:
            差分があれば Trueを返す

        """
        logger.info("=== プロジェクト設定の差分 ===")

        config1 = self.service.api.get_project(project_id1)[0]["configuration"]
        config2 = self.service.api.get_project(project_id2)[0]["configuration"]

        # ignored_key = {"updated_datetime", "created_datetime", "project_id"}
        diff_result = list(dictdiffer.diff(config1, config2))
        if len(diff_result) > 0:
            print("プロジェクト設定に差分あり")
            pprint.pprint(diff_result)
            return True
        else:
            logger.info("プロジェクト設定は同じ")
            return False

    def validate_projects(self, project_id1: str, project_id2: str):
        """
        適切なRoleが付与されているかを確認する。
        Args:
            project_id1:　
            project_id2:　

        Raises:
             AuthorizationError: 自分自身のRoleがいずれかのRoleにも合致しなければ、AuthorizationErrorが発生する。

        """

        roles = [ProjectMemberRole.OWNER, ProjectMemberRole.ACCEPTER, ProjectMemberRole.TRAINING_DATA_USER]
        super().validate_project(project_id1, roles)
        super().validate_project(project_id2, roles)

    def main(self):
        args = self.args
        project_id1 = args.project_id1
        project_id2 = args.project_id2

        logger.info(f"=== {self.project_title1}({project_id1}) と {self.project_title2}({project_id1}) の差分を表示")

        self.validate_projects(project_id1, project_id2)

        diff_targets = args.target
        if "members" in diff_targets:
            self.diff_project_members(project_id1, project_id2)

        if "settings" in diff_targets:
            self.diff_project_settingss(project_id1, project_id2)

        if "annotation_labels" in diff_targets or "inspection_phrases" in diff_targets:
            self.diff_annotation_specs(project_id1, project_id2, diff_targets)


def parse_args(parser: argparse.ArgumentParser):
    parser.add_argument('project_id1', type=str, help='比較対象のプロジェクトのproject_id')

    parser.add_argument('project_id2', type=str, help='比較対象のプロジェクトのproject_id')

    parser.add_argument(
        '--target', type=str, nargs="+", choices=["annotation_labels", "inspection_phrases", "members", "settings"],
        default=["annotation_labels", "inspection_phrases", "members", "settings"], help='比較する項目。指定しなければ全項目を比較する。'
        'annotation_labels: アノテーション仕様のラベル情報, '
        'inspection_phrases: 定型指摘,'
        'members: プロジェクトメンバ,'
        'settings: プロジェクト設定,')

    parser.set_defaults(subcommand_func=main)


def main(args):
    service = build_annofabapi_resource_and_login()
    facade = AnnofabApiFacade(service)
    DiffProjecs(service, facade, args).main()


def add_parser_deprecated(subparsers: argparse._SubParsersAction):
    subcommand_name = "diff_projects"
    subcommand_help = "プロジェクト間の差分を表示する。"
    description = ("プロジェクト間の差分を表示する。" "ただし、AnnoFabで生成されるIDや、変化する日時などは比較しない。")
    epilog = "オーナ、チェッカーロールのいずれかを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "diff"
    subcommand_help = "プロジェクト間の差分を表示する。"
    description = ("プロジェクト間の差分を表示する。" "ただし、AnnoFabで生成されるIDや、変化する日時などは比較しない。")
    epilog = "オーナ、チェッカーロールのいずれかを持つユーザで実行してください。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description, epilog=epilog)
    parse_args(parser)
