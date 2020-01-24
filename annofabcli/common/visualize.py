"""
annofabapiのfacadeクラス
"""

import enum
from typing import Any, Dict, List, Optional

import annofabapi
import more_itertools
from annofabapi.models import (
    AnnotationSpecsHistory,
    InputData,
    Inspection,
    OrganizationMember,
    Task,
    TaskHistoryShort,
    TaskPhase,
)


class MessageLocale(enum.Enum):
    EN = "en-US"
    JA = "ja-JP"


class AddProps:
    """
    WebAPIから取得したコンテンツに、属性を付与する。
    """

    #: 組織メンバ一覧のキャッシュ
    _organization_members: Optional[List[OrganizationMember]] = None

    def __init__(self, service: annofabapi.Resource, project_id: str):
        self.service = service
        self.project_id = project_id
        self.organization_name = self._get_organization_name_from_project_id(project_id)

        annotation_specs, _ = self.service.api.get_annotation_specs(project_id)
        self.specs_labels: List[Dict[str, Any]] = annotation_specs["labels"]
        self.specs_inspection_phrases: List[Dict[str, Any]] = annotation_specs["inspection_phrases"]

    @staticmethod
    def millisecond_to_hour(millisecond: int):
        return millisecond / 1000 / 3600

    @staticmethod
    def get_message(i18n_messages: Dict[str, Any], locale: MessageLocale) -> Optional[str]:
        messages: List[Dict[str, Any]] = i18n_messages["messages"]
        dict_message = more_itertools.first_true(messages, pred=lambda e: e["lang"] == locale.value)
        if dict_message is not None:
            return dict_message["message"]
        else:
            return None

    @staticmethod
    def add_properties_of_project(target: Dict[str, Any], project_title: str) -> Dict[str, Any]:
        target["project_title"] = project_title
        return target

    def _add_user_info(self, target: Any):
        user_id = None
        username = None

        account_id = target["account_id"]
        if account_id is not None:
            member = self.get_organization_member_from_account_id(account_id)
            if member is not None:
                user_id = member["user_id"]
                username = member["username"]

        target["user_id"] = user_id
        target["username"] = username
        return target

    def get_organization_member_from_account_id(self, account_id: str) -> Optional[OrganizationMember]:
        """
        account_idから組織メンバを取得する.
        内部で保持している組織メンバ一覧を参照する。

        Args:
            project_id:
            accoaunt_id:

        Returns:
            組織メンバ
        """

        def update_organization_members():
            self._organization_members = self.service.wrapper.get_all_organization_members(self.organization_name)

        def get_member():
            member = more_itertools.first_true(self._organization_members, pred=lambda e: e["account_id"] == account_id)
            return member

        if self._organization_members is not None:
            member = get_member()
            if member is not None:
                return member

            else:
                update_organization_members()
                return get_member()

        else:
            update_organization_members()
            return get_member()

    def _get_organization_name_from_project_id(self, project_id: str) -> str:
        """
        project_Idから組織名を取得する。
        """
        organization, _ = self.service.api.get_organization_of_project(project_id)
        return organization["organization_name"]

    def get_phrase_name(self, phrase_id, locale: MessageLocale) -> Optional[str]:
        phrase: Optional[Dict[str, Any]] = more_itertools.first_true(
            self.specs_inspection_phrases, pred=lambda e: e["id"] == phrase_id
        )
        if phrase is None:
            return None

        return self.get_message(phrase["text"], locale)

    def get_label_name(self, label_id: str, locale: MessageLocale) -> Optional[str]:
        label = more_itertools.first_true(self.specs_labels, pred=lambda e: e["label_id"] == label_id)
        if label is None:
            return None

        return self.get_message(label["label_name"], locale)

    def add_properties_to_annotation_specs_history(
        self, annotation_specs_history: AnnotationSpecsHistory
    ) -> AnnotationSpecsHistory:
        """
        アノテーション仕様の履歴に、以下のキーを追加する.
        user_id
        username

        Args:
            annotation_specs_history:

        Returns:
            annotation_specs_history
        """
        return self._add_user_info(annotation_specs_history)

    def add_properties_to_inspection(
        self, inspection: Inspection, detail: Optional[Dict[str, Any]] = None
    ) -> Inspection:
        """
        検査コメントに、以下のキーを追加する.
        commenter_user_id
        commenter_username
        phrase_names_en
        phrase_names_ja
        label_name_en
        label_name_en

        Args:
            inspection:
            detail: 検査コメント情報に追加する詳細な情報

        Returns:

        """

        def add_commenter_info():
            commenter_user_id = None
            commenter_username = None

            commenter_account_id = inspection["commenter_account_id"]
            if commenter_account_id is not None:
                member = self.get_organization_member_from_account_id(commenter_account_id)
                if member is not None:
                    commenter_user_id = member["user_id"]
                    commenter_username = member["username"]

            inspection["commenter_user_id"] = commenter_user_id
            inspection["commenter_username"] = commenter_username

        add_commenter_info()
        inspection["phrase_names_en"] = [self.get_phrase_name(e, MessageLocale.EN) for e in inspection["phrases"]]
        inspection["phrase_names_ja"] = [self.get_phrase_name(e, MessageLocale.JA) for e in inspection["phrases"]]

        inspection["label_name_en"] = self.get_label_name(inspection["label_id"], MessageLocale.EN)
        inspection["label_name_ja"] = self.get_label_name(inspection["label_id"], MessageLocale.JA)

        if detail is not None:
            inspection.update(detail)

        return inspection

    def add_properties_to_task(self, task: Task) -> Task:
        """
        タスク情報に、以下のキーを追加する.

        * user_id
        * username
        * worktime_hour
        * number_of_rejections_by_inspection
        * number_of_rejections_by_acceptance

        Args:
            task:

        Returns:
            Task情報

        """

        self._add_user_info(task)
        task["worktime_hour"] = self.millisecond_to_hour(task["work_time_span"])

        histories = [self._add_user_info(e) for e in task["histories_by_phase"]]
        task["histories_by_phase"] = histories

        task["number_of_rejections_by_inspection"] = self.get_number_of_rejections_by_phase(
            TaskPhase.INSPECTION, histories
        )
        task["number_of_rejections_by_acceptance"] = self.get_number_of_rejections_by_phase(
            TaskPhase.ACCEPTANCE, histories
        )

        return task

    @staticmethod
    def add_properties_to_input_data(input_data: InputData, task_id_list: List[str]) -> InputData:
        """
        入力データ情報に、以下のキーを追加する。

        * parent_task_id_list

        Args:
            input_data:
            task_id_list:

        Returns:
            入力データ情報

        """
        input_data["parent_task_id_list"] = task_id_list
        return input_data

    @staticmethod
    def get_number_of_rejections_by_phase(phase: TaskPhase, task_histories: List[TaskHistoryShort]) -> int:
        """
        phaseごとの差し戻し回数を算出する

        Args:
            phase:
            task_histories:

        Returns:
            差し戻し回数

        """

        rejections_by_phase = 0
        for i, history in enumerate(task_histories):
            if history["phase"] != phase.value:
                continue

            if i + 1 < len(task_histories) and task_histories[i + 1]["phase"] == TaskPhase.ANNOTATION.value:
                rejections_by_phase += 1

        return rejections_by_phase
