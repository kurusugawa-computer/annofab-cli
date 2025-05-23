from __future__ import annotations

import enum
from typing import Any, Optional

import annofabapi
import more_itertools
from annofabapi.models import (
    AnnotationSpecsHistory,
    Inspection,
    OrganizationMember,
    ProjectMember,
    SingleAnnotation,
    Task,
    TaskHistory,
    TaskPhase,
)
from annofabapi.utils import get_number_of_rejections

from annofabcli.common.facade import convert_annotation_specs_labels_v2_to_v1
from annofabcli.common.utils import isoduration_to_hour


class MessageLocale(enum.Enum):
    EN = "en-US"
    JA = "ja-JP"


class AddProps:
    """
    WebAPIから取得したコンテンツに、属性を付与する。
    """

    #: 組織メンバ一覧のキャッシュ
    _organization_members: Optional[list[OrganizationMember]] = None
    _project_member_list: Optional[list[ProjectMember]] = None

    def __init__(self, service: annofabapi.Resource, project_id: str) -> None:
        self.service = service
        self.project_id = project_id

        self._specs_labels: Optional[list[dict[str, Any]]] = None
        self._specs_inspection_phrases: Optional[list[dict[str, Any]]] = None

    def _set_annotation_specs(self):  # noqa: ANN202
        """
        アノテーション仕様に関する情報をインスタンス変数に格納します。
        """
        annotation_specs, _ = self.service.api.get_annotation_specs(self.project_id, query_params={"v": "2"})
        self._specs_labels = convert_annotation_specs_labels_v2_to_v1(labels_v2=annotation_specs["labels"], additionals_v2=annotation_specs["additionals"])
        self._specs_inspection_phrases = annotation_specs["inspection_phrases"]

    @property
    def specs_labels(self) -> list[dict[str, Any]]:
        """
        アノテーション仕様のラベルのlistを返します。
        ラベルの中に属性情報が格納されています。

        Returns:
            アノテーション仕様のラベルlist
        """
        if self._specs_labels is not None:
            return self._specs_labels

        self._set_annotation_specs()
        return self.specs_labels

    @property
    def specs_inspection_phrases(self) -> list[dict[str, Any]]:
        """
        アノテーション仕様の定型指摘のlistを返します。

        Returns:
            アノテーション仕様の定型指摘のlist
        """
        if self._specs_inspection_phrases is not None:
            return self._specs_inspection_phrases

        self._set_annotation_specs()
        return self.specs_inspection_phrases

    @staticmethod
    def millisecond_to_hour(millisecond: int) -> float:
        return millisecond / 1000 / 3600

    @staticmethod
    def get_message(i18n_messages: dict[str, Any], locale: MessageLocale) -> Optional[str]:
        messages: list[dict[str, Any]] = i18n_messages["messages"]
        dict_message = more_itertools.first_true(messages, pred=lambda e: e["lang"] == locale.value)
        if dict_message is not None:
            return dict_message["message"]
        else:
            return None

    @staticmethod
    def add_properties_of_project(target: dict[str, Any], project_title: str) -> dict[str, Any]:
        target["project_title"] = project_title
        return target

    def _add_user_info(self, target: dict[str, Any]) -> dict[str, Any]:
        user_id = None
        username = None

        account_id = target["account_id"]
        if account_id is not None:
            member = self.get_project_member_from_account_id(account_id)
            if member is not None:
                user_id = member["user_id"]
                username = member["username"]

        target["user_id"] = user_id
        target["username"] = username
        return target

    def get_project_member_from_account_id(self, account_id: str) -> Optional[ProjectMember]:
        if self._project_member_list is None:
            project_member_list = self.service.wrapper.get_all_project_members(self.project_id, query_params={"include_inactive_member": True})
            self._project_member_list = project_member_list
        else:
            project_member_list = self._project_member_list

        return more_itertools.first_true(project_member_list, pred=lambda e: e["account_id"] == account_id)

    def _get_organization_name_from_project_id(self, project_id: str) -> str:
        """
        project_Idから組織名を取得する。
        """
        organization, _ = self.service.api.get_organization_of_project(project_id)
        return organization["organization_name"]

    def get_phrase_name(self, phrase_id: str, locale: MessageLocale) -> Optional[str]:
        phrase: Optional[dict[str, Any]] = more_itertools.first_true(self.specs_inspection_phrases, pred=lambda e: e["id"] == phrase_id)
        if phrase is None:
            return None

        return self.get_message(phrase["text"], locale)

    def get_label_name(self, label_id: str, locale: MessageLocale) -> Optional[str]:
        label = more_itertools.first_true(self.specs_labels, pred=lambda e: e["label_id"] == label_id)
        if label is None:
            return None

        return self.get_message(label["label_name"], locale)

    def get_additional_data_name(self, additional_data_definition_id: str, locale: MessageLocale, label_id: Optional[str] = None) -> Optional[str]:
        def _get_additional_data_name(arg_additional_data_definitions: list[dict[str, Any]]) -> Optional[str]:
            additional_data = more_itertools.first_true(
                arg_additional_data_definitions,
                pred=lambda e: e["additional_data_definition_id"] == additional_data_definition_id,
            )
            if additional_data is None:
                return None
            return self.get_message(additional_data["name"], locale)

        if label_id is not None:
            label = more_itertools.first_true(self.specs_labels, pred=lambda e: e["label_id"] == label_id)
            if label is None:
                return None
            else:
                return _get_additional_data_name(label["additional_data_definitions"])
        else:
            for label in self.specs_labels:
                additional_data_name = _get_additional_data_name(label["additional_data_definitions"])
                if additional_data_name is not None:
                    return additional_data_name

            return None

    def add_properties_to_annotation_specs_history(self, annotation_specs_history: AnnotationSpecsHistory) -> AnnotationSpecsHistory:
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

    def add_properties_to_instruction(self, instruction_history: AnnotationSpecsHistory) -> AnnotationSpecsHistory:
        """
        作業ガイド履歴に、以下のキーを追加する.
        user_id
        username

        Args:
            instruction_history:

        Returns:
            instruction_history
        """
        return self._add_user_info(instruction_history)

    def add_properties_to_inspection(self, inspection: Inspection, detail: Optional[dict[str, Any]] = None) -> Inspection:
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

        def add_commenter_info():  # noqa: ANN202
            commenter_user_id = None
            commenter_username = None

            commenter_account_id = inspection["commenter_account_id"]
            if commenter_account_id is not None:
                member = self.get_project_member_from_account_id(commenter_account_id)
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

    def add_properties_to_comment(self, comment: dict[str, Any]) -> dict[str, Any]:
        """
        検査コメントに、以下のキーを追加する.
        user_id
        username
        phrase_names_en
        phrase_names_ja
        label_name_en
        label_name_en

        Args:
            comment:

        Returns:

        """

        def add_commenter_info():  # noqa: ANN202
            commenter_user_id = None
            commenter_username = None

            commenter_account_id = comment["account_id"]
            if commenter_account_id is not None:
                member = self.get_project_member_from_account_id(commenter_account_id)
                if member is not None:
                    commenter_user_id = member["user_id"]
                    commenter_username = member["username"]

            comment["user_id"] = commenter_user_id
            comment["username"] = commenter_username

        add_commenter_info()

        comment["phrase_names_en"] = [self.get_phrase_name(e, MessageLocale.EN) for e in comment["phrases"]]
        comment["phrase_names_ja"] = [self.get_phrase_name(e, MessageLocale.JA) for e in comment["phrases"]]

        comment_node = comment["comment_node"]
        if "label_id" in comment_node:
            comment_node["label_name_en"] = self.get_label_name(comment_node["label_id"], MessageLocale.EN)
            comment_node["label_name_ja"] = self.get_label_name(comment_node["label_id"], MessageLocale.JA)

        return comment

    def add_properties_to_single_annotation(self, annotation: SingleAnnotation) -> SingleAnnotation:
        """
        アノテーション情報（details）検査コメントに、以下のキーを追加する.
        detail.label_name_en
        detail.user_id
        detail.username

        Args:
            annotation: アノテーション

        Returns:
            情報が追加されたアノテーション
        """
        detail = annotation["detail"]
        detail["label_name_en"] = self.get_label_name(detail["label_id"], MessageLocale.EN)

        account_id = detail["account_id"]
        user_id = None
        username = None
        if account_id is not None:
            member = self.get_project_member_from_account_id(account_id)
            if member is not None:
                user_id = member["user_id"]
                username = member["username"]

        detail["user_id"] = user_id
        detail["username"] = username

        return annotation

    def add_properties_to_task(self, task: Task) -> Task:
        """
        タスク情報に、以下のキーを追加する.

        * user_id
        * username
        * worktime_hour
        * number_of_rejections_by_inspection
        * number_of_rejections_by_acceptance
        * input_data_count

        以下のキーを削除する。
        * number_of_rejections


        Args:
            task:

        Returns:
            Task情報

        """

        self._add_user_info(task)
        task["worktime_hour"] = self.millisecond_to_hour(task["work_time_span"])

        histories = [self._add_user_info(e) for e in task["histories_by_phase"]]
        task["histories_by_phase"] = histories

        task["number_of_rejections_by_inspection"] = get_number_of_rejections(histories, TaskPhase.INSPECTION)
        task["number_of_rejections_by_acceptance"] = get_number_of_rejections(histories, TaskPhase.ACCEPTANCE)

        # number_of_rejectionsは非推奨なプロパティで、number_of_rejections_by_inspection/number_of_rejections_by_acceptanceと矛盾する場合があるので、削除する
        task.pop("number_of_rejections", None)

        task["input_data_count"] = len(task["input_data_id_list"])
        return task

    def add_properties_to_task_history(self, task_history: TaskHistory) -> TaskHistory:
        """
        タスク履歴情報に、以下のキーを追加する.

        * user_id
        * username
        * worktime_hour

        Args:
            task:

        Returns:
            Task情報

        """

        self._add_user_info(task_history)
        task_history["worktime_hour"] = isoduration_to_hour(task_history["accumulated_labor_time_milliseconds"])
        return task_history

    def add_properties_to_task_history_event(self, task_history_event: dict[str, Any]) -> dict[str, Any]:
        """
        タスク履歴イベント情報に、以下のキーを追加する.

        * user_id
        * username

        Args:
            task:

        Returns:
            Task情報

        """
        self._add_user_info(task_history_event)
        return task_history_event
