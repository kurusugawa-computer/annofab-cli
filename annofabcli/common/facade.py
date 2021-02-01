import logging
from dataclasses import asdict, dataclass
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
    ProjectId,
    ProjectMember,
    ProjectMemberRole,
    SingleAnnotation,
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

    if task_query.phase is not None and annotation["task_phase"] != task_query.phase:
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


class AnnofabApiFacade:
    """
    AnnofabApiのFacadeクラス。annofabapiの複雑な処理を簡単に呼び出せるようにする。
    """

    #: 組織メンバ一覧のキャッシュ
    _organization_members: Optional[Tuple[ProjectId, List[OrganizationMember]]] = None

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

    def get_organization_member_from_account_id(self, project_id: str, account_id: str) -> Optional[OrganizationMember]:
        """
        account_idから組織メンバを取得する。
        インスタンス変数に組織メンバがあれば、WebAPIは実行しない。

        Args:
            project_id:
            accoaunt_id:

        Returns:
            組織メンバ。見つからない場合はNone
        """
        return self._get_organization_member_with_predicate(project_id, lambda e: e["account_id"] == account_id)

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
            accoaunt_id:

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
        usre_idからaccount_idを取得する。
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

    def change_operator_of_task(
        self, project_id: str, task_id: str, account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        タスクの担当者を変更する
        Args:
            self:
            project_id:
            task_id:
            account_id: 新しい担当者のuser_id. Noneの場合未割り当てになる。

        Returns:
            変更後のtask情報

        """
        task, _ = self.service.api.get_task(project_id, task_id)

        req = {
            "status": "not_started",
            "account_id": account_id,
            "last_updated_datetime": task["updated_datetime"],
        }
        return self.service.api.operate_task(project_id, task_id, request_body=req)[0]

    def change_to_working_status(self, project_id: str, task_id: str, account_id: str) -> Dict[str, Any]:
        """
        タスクを作業中に変更する
        Args:
            self:
            project_id:
            task_id:
            account_id:

        Returns:
            変更後のtask情報

        """
        task, _ = self.service.api.get_task(project_id, task_id)
        req = {
            "status": "working",
            "account_id": account_id,
            "last_updated_datetime": task["updated_datetime"],
        }
        return self.service.api.operate_task(project_id, task_id, request_body=req)[0]

    def change_to_break_phase(self, project_id: str, task_id: str) -> Dict[str, Any]:
        """
        タスクを休憩中に変更する
        Returns:
            変更後のtask情報
        """
        task, _ = self.service.api.get_task(project_id, task_id)

        req = {
            "status": "break",
            "account_id": self.service.api.account_id,
            "last_updated_datetime": task["updated_datetime"],
        }
        return self.service.api.operate_task(project_id, task_id, request_body=req)[0]

    def reject_task(
        self, project_id: str, task_id: str, account_id: str, annotator_account_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        タスクを強制的に差し戻し、annotator_account_id　に担当を割り当てる。

        Args:
            task_id:
            account_id: 差し戻すときのユーザのaccount_id
            annotator_account_id: 差し戻したあとに割り当てるユーザ。Noneの場合は直前のannotation phase担当者に割り当てる。

        Returns:
            変更あとのtask情報

        """

        # タスクを差し戻す
        task, _ = self.service.api.get_task(project_id, task_id)

        req_reject = {
            "status": "rejected",
            "account_id": account_id,
            "last_updated_datetime": task["updated_datetime"],
            "force": True,
        }
        rejected_task, _ = self.service.api.operate_task(project_id, task_id, request_body=req_reject)

        req_change_operator = {
            "status": "not_started",
            "account_id": annotator_account_id,
            "last_updated_datetime": rejected_task["updated_datetime"],
        }
        updated_task, _ = self.service.api.operate_task(project_id, task["task_id"], request_body=req_change_operator)
        return updated_task

    def reject_task_assign_last_annotator(self, project_id: str, task_id: str) -> Dict[str, Any]:
        """
        タスクを差し戻したあとに、最後のannotation phase担当者に割り当てる。

        Args:
            task_id:
            account_id: 差し戻すときのユーザのaccount_id

        Returns:
            変更後のtask情報

        """

        task, _ = self.service.api.get_task(project_id, task_id)
        req_reject = {
            "status": "rejected",
            "account_id": self.service.api.account_id,
            "last_updated_datetime": task["updated_datetime"],
            "force": True,
        }
        rejected_task, _ = self.service.api.operate_task(project_id, task_id, request_body=req_reject)
        # 強制的に差し戻すと、タスクの担当者は直前の教師付け(annotation)フェーズの担当者を割り当てられるので、`operate_task`を実行しない。
        return rejected_task

    def complete_task(self, project_id: str, task_id: str) -> Dict[str, Any]:
        """
        タスクを完了状態にする。
        注意：サーバ側ではタスクの検査は実施されない。
        タスクを完了状態にする前にクライアント側であらかじめ「タスクの自動検査」を実施する必要がある。
        """
        task, _ = self.service.api.get_task(project_id, task_id)

        req = {
            "status": "complete",
            "account_id": self.service.api.account_id,
            "last_updated_datetime": task["updated_datetime"],
        }
        return self.service.api.operate_task(project_id, task_id, request_body=req)[0]

    @staticmethod
    def get_label_info_from_name(annotation_specs_labels: List[Dict[str, Any]], label_name_en: str) -> Dict[str, Any]:
        labels = [e for e in annotation_specs_labels if AnnofabApiFacade.get_label_name_en(e) == label_name_en]
        if len(labels) > 1:
            raise ValueError(f"label_name_en: {label_name_en} に一致するラベル情報が複数見つかりました。")

        if len(labels) == 0:
            raise ValueError(f"label_name_en: {label_name_en} に一致するラベル情報が見つかりませんでした。")

        return labels[0]

    @staticmethod
    def get_additional_data_from_name(
        additional_data_definitions: List[Dict[str, Any]], additional_data_definition_name_en: str
    ) -> Dict[str, Any]:
        additional_data_list = [
            e
            for e in additional_data_definitions
            if AnnofabApiFacade.get_additional_data_definition_name_en(e) == additional_data_definition_name_en
        ]
        if len(additional_data_list) > 1:
            raise ValueError(
                f"additional_data_definition_name_en: {additional_data_definition_name_en} に一致する属性情報が複数見つかりました。"
            )

        if len(additional_data_list) == 0:
            raise ValueError(
                f"additional_data_definition_name_en: {additional_data_definition_name_en} に一致する属性情報が見つかりませんでした。"
            )

        return additional_data_list[0]

    @staticmethod
    def get_choice_info_from_name(choice_info_list: List[Dict[str, Any]], choice_name_en: str) -> Dict[str, Any]:
        filterd_choice_list = [e for e in choice_info_list if AnnofabApiFacade.get_choice_name_en(e) == choice_name_en]
        if len(filterd_choice_list) > 1:
            raise ValueError(f"choice_name_en: {choice_name_en} に一致する選択肢情報が複数見つかりました。")

        if len(filterd_choice_list) == 0:
            raise ValueError(f"choice_name_en: {choice_name_en} に一致する選択肢情報が見つかりませんでした。")

        return filterd_choice_list[0]

    def to_annotation_query_from_cli(self, project_id: str, query: AnnotationQueryForCli) -> AnnotationQuery:
        """
        コマンドラインから指定されたアノテーション検索クエリを、WebAPIに渡す検索クエリに変換する。
        nameからIDを取得できない場合は、その時点で終了する。

        * ``label_name_en`` から ``label_id`` に変換する。
        * ``additional_data_definition_name_en`` から ``additional_data_definition_id`` に変換する。
        * ``choice_name_en`` から ``choice`` に変換する。

        Args:
            project_id:
            annotation_query:
            task_id: 検索対象のtask_id

        Returns:
            修正したタスク検索クエリ

        """

        annotation_specs, _ = self.service.api.get_annotation_specs(project_id)
        specs_labels = annotation_specs["labels"]

        # label_name_en から label_idを設定
        if query.label_id is not None:
            label_info = more_itertools.first_true(specs_labels, pred=lambda e: e["label_id"] == query.label_id)
            if label_info is None:
                raise ValueError(f"label_id: {query.label_id} に一致するラベル情報は見つかりませんでした。")
        elif query.label_name_en is not None:
            label_info = self.get_label_info_from_name(specs_labels, query.label_name_en)
        else:
            raise ValueError("'label_id' または 'label_name_en'のいずれかは必ず指定してください。")

        api_query = AnnotationQuery(label_id=label_info["label_id"])
        if query.attributes is not None:
            api_attirbutes = []
            for cli_attirbute in query.attributes:
                api_attirbutes.append(
                    self._get_attribute_from_cli(label_info["additional_data_definitions"], cli_attirbute)
                )

            api_query.attributes = api_attirbutes

        return api_query

    def to_attributes_from_cli(
        self, project_id: str, label_id: str, attributes: List[AdditionalDataForCli]
    ) -> List[AdditionalData]:
        """
        コマンドラインから指定された属性値Listを、WebAPIに渡す属性値Listに変換する。
        nameからIDを取得できない場合は、その時点で終了する。

        * ``additional_data_definition_name_en`` から ``additional_data_definition_id`` に変換する。
        * ``choice_name_en`` から ``choice`` に変換する。
        """
        annotation_specs, _ = self.service.api.get_annotation_specs(project_id)
        specs_labels = annotation_specs["labels"]

        # label_name_en から label_idを設定
        label_info = more_itertools.first_true(specs_labels, pred=lambda e: e["label_id"] == label_id)
        if label_info is None:
            raise ValueError(f"label_id: {label_id} に一致するラベル情報は見つかりませんでした。")

        api_attirbutes = []
        for cli_attirbute in attributes:
            api_attirbutes.append(
                self._get_attribute_from_cli(label_info["additional_data_definitions"], cli_attirbute)
            )
        return api_attirbutes

    @staticmethod
    def _get_attribute_from_cli(
        additional_data_definitions: List[Dict[str, Any]], cli_attirbute: AdditionalDataForCli
    ) -> AdditionalData:

        if cli_attirbute.additional_data_definition_id is not None:
            additional_data = more_itertools.first_true(
                additional_data_definitions,
                pred=lambda e: e["additional_data_definition_id"] == cli_attirbute.additional_data_definition_id,
            )
            if additional_data is None:
                raise ValueError(
                    f"additional_data_definition_id: {cli_attirbute.additional_data_definition_id} は存在しない値です。"
                )

        elif cli_attirbute.additional_data_definition_name_en is not None:
            additional_data = AnnofabApiFacade.get_additional_data_from_name(
                additional_data_definitions, cli_attirbute.additional_data_definition_name_en
            )

        else:
            raise ValueError(
                "'additional_data_definition_id' または 'additional_data_definition_name_en'のいずれかは必ず指定してください。"
            )

        api_attirbute = AdditionalData(
            additional_data_definition_id=additional_data["additional_data_definition_id"],
            flag=cli_attirbute.flag,
            integer=cli_attirbute.integer,
            comment=cli_attirbute.comment,
            choice=cli_attirbute.choice,
        )

        # 選択肢IDを確認
        choices = additional_data["choices"]
        if cli_attirbute.choice is not None:
            choice_info = more_itertools.first_true(choices, pred=lambda e: e["choice_id"] == cli_attirbute.choice)
            if choice_info is None:
                raise ValueError(f"choice: {cli_attirbute.choice} は存在しない値です。")

        elif cli_attirbute.choice_name_en is not None:
            choice_info = AnnofabApiFacade.get_choice_info_from_name(choices, cli_attirbute.choice_name_en)
            api_attirbute.choice = choice_info["choice_id"]

        return api_attirbute

    def get_annotation_list_for_task(
        self, project_id: str, task_id: str, query: Optional[AnnotationQuery] = None
    ) -> List[SingleAnnotation]:
        """
        タスク内のアノテーション一覧を取得する。

        Args:
            project_id:
            task_id:
            query: アノテーションの検索条件

        Returns:
            アノテーション一覧
        """
        dict_query = {"task_id": task_id, "exact_match_task_id": True}
        if query is not None:
            dict_query.update(asdict(query))
        query_params = {"query": dict_query}
        annotation_list = self.service.wrapper.get_all_annotation_list(project_id, query_params=query_params)
        assert all([e["task_id"] == task_id for e in annotation_list]), f"task_id='{task_id}' 以外のアノテーションが取得されています！！"
        return annotation_list

    def delete_annotation_list(
        self, project_id: str, annotation_list: List[SingleAnnotation]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        アノテーション一覧を削除する。
        【注意】取扱注意

        Args:
            project_id:
            annotation_list: アノテーション一覧

        Returns:
            `batch_update_annotations`メソッドのレスポンス

        """

        def _to_request_body_elm(annotation: Dict[str, Any]) -> Dict[str, Any]:
            detail = annotation["detail"]
            return {
                "project_id": annotation["project_id"],
                "task_id": annotation["task_id"],
                "input_data_id": annotation["input_data_id"],
                "updated_datetime": annotation["updated_datetime"],
                "annotation_id": detail["annotation_id"],
                "_type": "Delete",
            }

        request_body = [_to_request_body_elm(annotation) for annotation in annotation_list]
        return self.service.api.batch_update_annotations(project_id, request_body)[0]

    def change_annotation_attributes(
        self, project_id: str, annotation_list: List[SingleAnnotation], attributes: List[AdditionalData]
    ) -> Optional[List[Dict[str, Any]]]:
        """
        アノテーション属性値を変更する。

        【注意】取扱注意

        Args:
            project_id:
            annotation_list: 変更対象のアノテーション一覧
            attributes: 変更後の属性値

        Returns:
            `batch_update_annotations`メソッドのレスポンス

        """

        def _to_request_body_elm(annotation: Dict[str, Any]) -> Dict[str, Any]:
            detail = annotation["detail"]
            return {
                "data": {
                    "project_id": annotation["project_id"],
                    "task_id": annotation["task_id"],
                    "input_data_id": annotation["input_data_id"],
                    "updated_datetime": annotation["updated_datetime"],
                    "annotation_id": detail["annotation_id"],
                    "label_id": detail["label_id"],
                    "additional_data_list": attributes_for_dict,
                },
                "_type": "Put",
            }

        attributes_for_dict: List[Dict[str, Any]] = [asdict(e) for e in attributes]
        request_body = [_to_request_body_elm(annotation) for annotation in annotation_list]
        return self.service.api.batch_update_annotations(project_id, request_body)[0]

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
