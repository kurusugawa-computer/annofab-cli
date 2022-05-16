import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import annofabapi
import annofabapi.utils
import more_itertools
from annofabapi.dataclass.annotation import AdditionalData
from annofabapi.dataclass.input import InputData
from annofabapi.dataclass.task import Task
from annofabapi.models import (
    OrganizationMember,
    OrganizationMemberRole,
    ProjectMember,
    ProjectMemberRole,
    TaskPhase,
    TaskStatus,
)
from dataclasses_json import DataClassJsonMixin

from annofabcli.common.exceptions import OrganizationAuthorizationError, ProjectAuthorizationError

logger = logging.getLogger(__name__)


@dataclass
class AnnotationQuery(DataClassJsonMixin):
    """
    `get_annotation_list`メソッドに渡すアノテーション検索条件
    """

    label_id: str
    attributes: Optional[List[AdditionalData]] = None


@dataclass
class AdditionalDataForCli(DataClassJsonMixin):
    additional_data_definition_id: Optional[str] = None
    """属性ID"""

    additional_data_definition_name_en: Optional[str] = None
    """属性の英語名"""

    flag: Optional[bool] = None

    integer: Optional[int] = None

    comment: Optional[str] = None

    choice: Optional[str] = None
    """選択肢ID"""

    choice_name_en: Optional[str] = None
    """選択肢の英語名"""


@dataclass
class AnnotationQueryForCli(DataClassJsonMixin):
    """
    コマンドライン上で指定するアノテーション検索条件
    """

    label_name_en: Optional[str] = None
    """ラベルの英語名"""
    label_id: Optional[str] = None
    attributes: Optional[List[AdditionalDataForCli]] = None


@dataclass
class TaskQuery(DataClassJsonMixin):
    """
    コマンドライン上で指定するタスクの検索条件
    """

    task_id: Optional[str] = None
    phase: Optional[TaskPhase] = None
    status: Optional[TaskStatus] = None
    phase_stage: Optional[int] = None
    user_id: Optional[str] = None
    account_id: Optional[str] = None
    no_user: bool = False
    """Trueなら未割り当てのタスクで絞り込む"""


@dataclass
class InputDataQuery(DataClassJsonMixin):
    """
    コマンドライン上で指定する入力データの検索条件
    """

    input_data_id: Optional[str] = None
    input_data_name: Optional[str] = None
    input_data_path: Optional[str] = None


def match_annotation_with_task_query(annotation: Dict[str, Any], task_query: Optional[TaskQuery]) -> bool:
    """
    Simple Annotationが、タスククエリ条件に合致するか

    Args:
        annotation: Simple Annotation
        task_query: タスククエリ

    Returns:
        TrueならSimple Annotationがタスククエリ条件にが合致する
    """

    def match_str(name: str, query: str) -> bool:
        return query.lower() in name.lower()

    if task_query is None:
        return True

    if task_query.task_id is not None and not match_str(annotation["task_id"], task_query.task_id):
        return False

    if task_query.status is not None and annotation["task_status"] != task_query.status.value:
        return False

    if task_query.phase is not None and annotation["task_phase"] != task_query.phase.value:
        return False

    if task_query.phase_stage is not None and annotation["task_phase_stage"] != task_query.phase_stage:
        return False

    return True


def match_task_with_query(  # pylint: disable=too-many-return-statements
    task: Task, task_query: Optional[TaskQuery]
) -> bool:
    """
    タスク情報が、タスククエリ条件に合致するかどうか。
    taskにはuser_idを保持していてないので、user_idでは比較しない。

    Args:
        task:
        task_query: タスククエリ検索条件。Noneの場合trueを返す。

    Returns:
        trueならタスククエリ条件に合致する。
    """

    def match_str(name: str, query: str, ignore_case: bool) -> bool:
        if ignore_case:
            return query.lower() in name.lower()
        else:
            return query in name

    if task_query is None:
        return True

    if task_query.task_id is not None and not match_str(task.task_id, task_query.task_id, ignore_case=True):
        return False

    if task_query.status is not None and task.status != task_query.status:
        return False

    if task_query.phase is not None and task.phase != task_query.phase:
        return False

    if task_query.phase_stage is not None and task.phase_stage != task_query.phase_stage:
        return False

    if task_query.no_user and task.account_id is not None:
        return False

    if task_query.account_id is not None and task.account_id != task_query.account_id:
        return False

    return True


def match_input_data_with_query(  # pylint: disable=too-many-return-statements
    input_data: InputData, input_data_query: Optional[InputDataQuery]
) -> bool:
    """
    入力データが、クエリ条件に合致するかどうか。

    Args:
        input_data:
        input_data_query: 入力データのクエリ検索条件。Noneの場合trueを返す。

    Returns:
        trueならクエリ条件に合致する。
    """

    def match_str(name: str, query: str, ignore_case: bool) -> bool:
        if ignore_case:
            return query.lower() in name.lower()
        else:
            return query in name

    if input_data_query is None:
        return True

    if input_data_query.input_data_id is not None and not match_str(
        input_data.input_data_id, input_data_query.input_data_id, ignore_case=True
    ):
        return False

    if input_data_query.input_data_name is not None and not match_str(
        input_data.input_data_name, input_data_query.input_data_name, ignore_case=True
    ):
        return False

    if input_data_query.input_data_path is not None and not match_str(
        input_data.input_data_path, input_data_query.input_data_path, ignore_case=False
    ):
        return False

    return True


def convert_annotation_specs_labels_v2_to_v1(
    labels_v2: List[Dict[str, Any]], additionals_v2: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """アノテーション仕様のV2版からV1版に変換する。V1版の方が扱いやすいので。

    Args:
        labels_v2 (List[Dict[str, Any]]): V2版のラベル情報
        additionals_v2 (List[Dict[str, Any]]): V2版の属性情報

    Returns:
        List[LabelV1]: V1版のラベル情報
    """

    def get_additional(additional_data_definition_id: str) -> Optional[Dict[str, Any]]:
        return more_itertools.first_true(
            additionals_v2, pred=lambda e: e["additional_data_definition_id"] == additional_data_definition_id
        )

    def to_label_v1(label_v2) -> Dict[str, Any]:
        additional_data_definition_id_list = label_v2["additional_data_definitions"]
        new_additional_data_definitions = []
        for additional_data_definition_id in additional_data_definition_id_list:
            additional = get_additional(additional_data_definition_id)
            if additional is not None:
                new_additional_data_definitions.append(additional)
            else:
                raise ValueError(
                    f"additional_data_definition_id='{additional_data_definition_id}' に対応する属性情報が存在しません。"
                    f"label_id='{label_v2['label_id']}', label_name_en='{AnnofabApiFacade.get_label_name_en(label_v2)}'"
                )
        label_v2["additional_data_definitions"] = new_additional_data_definitions
        return label_v2

    return [to_label_v1(label_v2) for label_v2 in labels_v2]


class AnnofabApiFacade:
    """
    AnnofabApiのFacadeクラス。annofabapiの複雑な処理を簡単に呼び出せるようにする。
    """

    #: 組織メンバ一覧のキャッシュ
    _organization_members: Optional[Tuple[str, List[OrganizationMember]]] = None

    _project_members_dict: Dict[str, List[ProjectMember]] = {}
    """プロジェクトメンバ一覧の情報。key:project_id, value:プロジェクトメンバ一覧"""

    def __init__(self, service: annofabapi.Resource):
        self.service = service

    @staticmethod
    def get_account_id_last_annotation_phase(task_histories: List[Dict[str, Any]]) -> Optional[str]:
        """
        タスク履歴の最後のannotation phaseを担当したaccount_idを取得する. なければNoneを返す
        Args:
            task_histories:

        Returns:


        """
        annotation_histories = [e for e in task_histories if e["phase"] == "annotation"]
        if len(annotation_histories) > 0:
            last_history = annotation_histories[-1]
            return last_history["account_id"]
        else:
            return None

    @staticmethod
    def get_label_name_en(label: Dict[str, Any]) -> str:
        """label情報から英語名を取得する"""
        label_name_messages = label["label_name"]["messages"]
        return [e["message"] for e in label_name_messages if e["lang"] == "en-US"][0]

    @staticmethod
    def get_additional_data_definition_name_en(additional_data_definition: Dict[str, Any]) -> str:
        """additional_data_definitionから英語名を取得する"""
        messages = additional_data_definition["name"]["messages"]
        return [e["message"] for e in messages if e["lang"] == "en-US"][0]

    @staticmethod
    def get_choice_name_en(choice: Dict[str, Any]) -> str:
        """choiceから英語名を取得する"""
        messages = choice["name"]["messages"]
        return [e["message"] for e in messages if e["lang"] == "en-US"][0]

    def get_project_title(self, project_id: str) -> str:
        """
        プロジェクトのタイトルを取得する
        Returns:
            プロジェクトのタイトル

        """
        project, _ = self.service.api.get_project(project_id)
        return project["title"]

    def _get_organization_member_with_predicate(
        self, project_id: str, predicate: Callable[[Any], bool]
    ) -> Optional[OrganizationMember]:
        """
        account_idから組織メンバを取得する。
        インスタンス変数に組織メンバがあれば、WebAPIは実行しない。

        Args:
            project_id:
            predicate: 組織メンバの検索条件

        Returns:
            組織メンバ。見つからない場合はNone
        """

        def update_organization_members():
            organization_name = self.get_organization_name_from_project_id(project_id)
            members = self.service.wrapper.get_all_organization_members(organization_name)
            self._organization_members = (project_id, members)

        if self._organization_members is not None:
            if self._organization_members[0] == project_id:
                member = more_itertools.first_true(self._organization_members[1], pred=predicate)
                return member

            else:
                # 別の組織の可能性があるので、再度組織メンバを取得する
                update_organization_members()
                return self._get_organization_member_with_predicate(project_id, predicate)

        else:
            update_organization_members()
            return self._get_organization_member_with_predicate(project_id, predicate)

    def _get_project_member_with_predicate(
        self, project_id: str, predicate: Callable[[Any], bool]
    ) -> Optional[ProjectMember]:
        """
        project_memberを取得する

        Args:
            project_id:
            predicate: 組織メンバの検索条件

        Returns:
            プロジェクトメンバ
        """
        project_member_list = self._project_members_dict.get(project_id)
        if project_member_list is None:
            project_member_list = self.service.wrapper.get_all_project_members(
                project_id, query_params={"include_inactive_member": True}
            )
            self._project_members_dict[project_id] = project_member_list
        return more_itertools.first_true(project_member_list, pred=predicate)

    def get_project_member_from_account_id(self, project_id: str, account_id: str) -> Optional[ProjectMember]:
        """
        account_idからプロジェクトメンバを取得する。

        Args:
            project_id:
            account_id:

        Returns:
            プロジェクトメンバ。見つからない場合はNone
        """
        return self._get_project_member_with_predicate(project_id, predicate=lambda e: e["account_id"] == account_id)

    def get_project_member_from_user_id(self, project_id: str, user_id: str) -> Optional[ProjectMember]:
        """
        user_idからプロジェクトメンバを取得する。

        Args:
            project_id:
            account_id:

        Returns:
            プロジェクトメンバ。見つからない場合はNone
        """
        return self._get_project_member_with_predicate(project_id, predicate=lambda e: e["user_id"] == user_id)

    def get_organization_member_from_user_id(self, project_id: str, user_id: str) -> Optional[OrganizationMember]:
        """
        user_idから組織メンバを取得する。
        インスタンス変数に組織メンバがあれば、WebAPIは実行しない。

        Args:
            project_id:
            user_id:

        Returns:
            組織メンバ
        """
        return self._get_organization_member_with_predicate(project_id, lambda e: e["user_id"] == user_id)

    def get_user_id_from_account_id(self, project_id: str, account_id: str) -> Optional[str]:
        """
        account_idからuser_idを取得する.
        インスタンス変数に組織メンバがあれば、WebAPIは実行しない。

        Args:
            project_id:
            account_id:

        Returns:
            user_id. 見つからなければNone

        """
        member = self.get_project_member_from_account_id(project_id, account_id)
        if member is None:
            return None
        else:
            return member.get("user_id")

    def get_account_id_from_user_id(self, project_id: str, user_id: str) -> Optional[str]:
        """
        user_idからaccount_idを取得する。
        インスタンス変数に組織メンバがあれば、WebAPIは実行しない。

        Args:
            project_id:
            user_id:

        Returns:
            account_id. 見つからなければNone

        """
        member = self.get_project_member_from_user_id(project_id, user_id)
        if member is None:
            return None
        else:
            return member.get("account_id")

    def get_organization_name_from_project_id(self, project_id: str) -> str:
        """
        project_Idから組織名を取得する。
        """
        organization, _ = self.service.api.get_organization_of_project(project_id)
        return organization["organization_name"]

    def get_organization_members_from_project_id(self, project_id: str) -> List[OrganizationMember]:
        organization_name = self.get_organization_name_from_project_id(project_id)
        return self.service.wrapper.get_all_organization_members(organization_name)

    def my_role_is_owner(self, project_id: str) -> bool:
        my_member, _ = self.service.api.get_my_member_in_project(project_id)
        return my_member["member_role"] == "owner"

    def contains_any_project_member_role(self, project_id: str, roles: List[ProjectMemberRole]) -> bool:
        """
        自分自身のプロジェクトメンバとしてのロールが、指定されたロールのいずれかに合致するかどうか
        Args:
            project_id:
            roles: ロール一覧

        Returns:
            Trueなら、自分自身のロールが、指定されたロールのいずれかに合致する。

        """
        my_member, _ = self.service.api.get_my_member_in_project(project_id)
        my_role = ProjectMemberRole(my_member["member_role"])
        return my_role in roles

    def contains_any_organization_member_role(
        self, organization_name: str, roles: List[OrganizationMemberRole]
    ) -> bool:
        """
        自分自身の組織メンバとしてのロールが、指定されたロールのいずれかに合致するかどうか
        Args:
            organization_name: 組織名
            roles: ロール一覧

        Returns:
            Trueなら、自分自身のロールが、指定されたロールのいずれかに合致する。
            Falseなら、ロールに合致しない or 組織に所属していない

        """
        my_organizations = self.service.wrapper.get_all_my_organizations()
        organization = more_itertools.first_true(my_organizations, pred=lambda e: e["name"] == organization_name)

        if organization is not None:
            my_role = OrganizationMemberRole(organization["my_role"])
            return my_role in roles
        else:
            return False

    ##################
    # operateTaskのfacade
    ##################
    def set_account_id_of_task_query(self, project_id: str, task_query: TaskQuery) -> TaskQuery:
        """
        タスククエリ条件のuser_idの値をaccount_idに設定する。

        Args:
            project_id:
            task_query:

        Returns:

        """
        if task_query.user_id is not None:
            task_query.account_id = self.get_account_id_from_user_id(project_id, task_query.user_id)
        return task_query

    def validate_project(
        self,
        project_id,
        project_member_roles: Optional[List[ProjectMemberRole]] = None,
        organization_member_roles: Optional[List[OrganizationMemberRole]] = None,
    ):
        """
        プロジェクト or 組織に対して、必要な権限が付与されているかを確認する。

        Args:
            project_id:
            project_member_roles: プロジェクトメンバロールの一覧. Noneの場合はチェックしない。
            organization_member_roles: 組織メンバロールの一覧。Noneの場合はチェックしない。

        Raises:
             AuthorizationError: 自分自身のRoleがいずれかのRoleにも合致しなければ、AuthorizationErrorが発生する。

        """
        project_title = self.get_project_title(project_id)
        logger.info(f"project_title = {project_title}, project_id = {project_id}")

        if project_member_roles is not None:
            if not self.contains_any_project_member_role(project_id, project_member_roles):
                raise ProjectAuthorizationError(project_title, project_member_roles)

        if organization_member_roles is not None:
            organization_name = self.get_organization_name_from_project_id(project_id)
            if not self.contains_any_organization_member_role(organization_name, organization_member_roles):
                raise OrganizationAuthorizationError(organization_name, organization_member_roles)
