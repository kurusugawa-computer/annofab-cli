"""
annofabapiのfacadeクラス
"""

from typing import Any, Callable, Dict, List, Optional, Tuple  # pylint: disable=unused-import

import annofabapi
import more_itertools
from annofabapi.models import ProjectMemberRole

class AnnofabApiFacade:
    """
    AnnofabApiのFacadeクラス。annofabapiの複雑な処理を簡単に呼び出せるようにする。
    """

    #: 組織メンバ一覧のキャッシュ
    _organization_members: List[Dict[str, Any]] = None

    def __init__(self, service: annofabapi.Resource):
        self.service = service

    @staticmethod
    def get_account_id_last_annotation_phase(task_histories: List[Dict[str, Any]]):
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
    def get_label_name_en(label: Dict[str, Any]):
        """label情報から英語名を取得する"""
        label_name_messages = label["label_name"]["messages"]
        return [e["message"] for e in label_name_messages if e["lang"] == "en-US"][0]

    def get_project_title(self, project_id: str) -> str:
        """
        プロジェクトのタイトルを取得する
        Returns:
            プロジェクトのタイトル

        """
        project, _ = self.service.api.get_project(project_id)
        return project['title']

    def get_my_account_id(self) -> str:
        """
        自分自身のaccount_idを取得する
        Returns:
            account_id

        """
        account, _ = self.service.api.get_my_account()
        return account['account_id']

    def get_account_id_from_user_id(self, project_id: str, user_id: str) -> str:
        """
        usre_idからaccount_idを取得する
        Args:
            project_id:
            user_id:

        Returns:
            account_id

        """
        member, _ = self.service.api.get_project_member(project_id, user_id)
        return member['account_id']

    def get_organization_member_from_account_id(self, project_id: str, account_id: str) -> Dict[str, Any]:
        """
        account_idからuser_idを取得する.
        内部で組織メンバを保持する。
        Args:
            project_id:
            accoaunt_id:

        Returns:
            account_id
        """

    def get_user_id_from_account_id(self, project_id: str, account_id: str) -> str:
        """
        account_idからuser_idを取得する.
        内部で組織メンバを保持する。
        Args:
            project_id:
            accoaunt_id:

        Returns:
            account_id

        """

        def update_organization_members():
            organization_name = self.get_organization_name_from_project_id(project_id)
            self._organization_members = self.service.wrapper.get_all_organization_members(organization_name)


        if self._organization_members is not None:
            member = more_itertools.first_true(self._organization_members, pred=lambda e: e["account_id"] == account_id)
            if member is not None:
                return member["user_id"]

            else:
                update_organization_members()
                return self.get_user_id_from_account_id(project_id, account_id)

        else:
            update_organization_members()
            return self.get_user_id_from_account_id(project_id, account_id)

    def get_organization_name_from_project_id(self, project_id: str) -> str:
        """
        project_Idから組織名を取得する。
        """
        organization, _ = self.service.api.get_organization_of_project(project_id)
        return organization["organization_name"]


    def my_role_is_owner(self, project_id: str) -> bool:
        my_member, _ = self.service.api.get_my_member_in_project(project_id)
        return my_member["member_role"] == "owner"

    def contains_anys_role(self, project_id: str, roles: List[ProjectMemberRole]) -> bool:
        """
        自分自身のプロジェクトメンバとしてのロールが、指定されたロールのいずれかに合致するかどうか
        Args:
            project_id:
            roles: ロール一覧

        Returns:
            Trueなら、自分自身のロールが、指定されたロールのいずれかに合致する。

        """
        my_member, _ = self.service.api.get_my_member_in_project(project_id)
        my_role = my_member["member_role"]
        return ProjectMemberRole(my_role) in roles

    ##################
    # operateTaskのfacade
    ##################

    def change_operator_of_task(self, project_id: str, task_id: str, account_id: str) -> Dict[str, Any]:
        """
        タスクの担当者を変更する
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
            "status": "not_started",
            "account_id": account_id,
            "last_updated_datetime": task["updated_datetime"],
        }
        return self.service.api.operate_task(project_id, task_id, request_body=req)[0]

    def change_to_working_phase(self, project_id: str, task_id: str, account_id: str) -> Dict[str, Any]:
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

    def change_to_break_phase(self, project_id: str, task_id: str, account_id: str) -> Dict[str, Any]:
        """
        タスクを休憩中に変更する
        Returns:
            変更後のtask情報
        """
        task, _ = self.service.api.get_task(project_id, task_id)

        req = {
            "status": "break",
            "account_id": account_id,
            "last_updated_datetime": task["updated_datetime"],
        }
        return self.service.api.operate_task(project_id, task_id, request_body=req)[0]

    def reject_task(self, project_id: str, task_id: str, account_id: str,
                    annotator_account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        タスクを差し戻し、annotator_account_id　に担当を割り当てる。
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
        }
        rejected_task, _ = self.service.api.operate_task(project_id, task_id, request_body=req_reject)

        req_change_operator = {
            "status": "not_started",
            "account_id": annotator_account_id,
            "last_updated_datetime": rejected_task["updated_datetime"],
        }
        updated_task, _ = self.service.api.operate_task(project_id, task["task_id"], request_body=req_change_operator)
        return updated_task

    def reject_task_assign_last_annotator(self, project_id: str, task_id: str, account_id: str) -> Tuple[Dict[str, Any], str]:
        """
        タスクを差し戻したあとに、最後のannotation phase担当者に割り当てる。

        Args:
            task_id:
            account_id: 差し戻すときのユーザのaccount_id

        Returns:
            Tuple[変更後のtask情報, 差し戻したタスクの担当者のaccount_id]

        """

        # タスクを差し戻す
        task, _ = self.service.api.get_task(project_id, task_id)
        last_annotator_account_id = self.get_account_id_last_annotation_phase(task["histories_by_phase"])
        updated_task = self.reject_task(project_id, task_id, account_id, last_annotator_account_id)
        return updated_task, last_annotator_account_id


    def complete_task(self, project_id: str, task_id: str, account_id: str) -> Dict[str, Any]:
        """
        タスクを完了状態にする。
        注意：サーバ側ではタスクの検査は実施されない。
        タスクを完了状態にする前にクライアント側であらかじめ「タスクの自動検査」を実施する必要がある。
        """
        task, _ = self.service.api.get_task(project_id, task_id)

        req = {
            "status": "complete",
            "account_id": account_id,
            "last_updated_datetime": task["updated_datetime"],
        }
        return self.service.api.operate_task(project_id, task_id, request_body=req)[0]
