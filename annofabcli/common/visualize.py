"""
annofabapiのfacadeクラス
"""

import enum
from typing import Any, Callable, Dict, List, Optional, Tuple  # pylint: disable=unused-import

import annofabapi
import more_itertools
from annofabapi.models import Inspection, OrganizationMember, ProjectMemberRole


class MessageLocale(enum.Enum):
    EN = "en-US"
    JA = "ja-JP"


class AddProps:
    """
    WebAPIから取得したコンテンツに、属性を付与する。
    """

    #: 組織メンバ一覧のキャッシュ
    _organization_members: List[Dict[str, Any]] = None

    def __init__(self, service: annofabapi.Resource, project_id: str):
        self.service = service
        self.project_id = project_id
        self.organization_name = self._get_organization_name_from_project_id(project_id)

        annotation_specs, _ = self.service.api.get_annotation_specs(project_id)
        self.specs_labels = annotation_specs['labels']
        self.specs_inspection_phrases = annotation_specs['inspection_phrases']

    @staticmethod
    def get_message(i18n_messages: Dict[str, Any], locale: MessageLocale) -> str:
        messages: List[Dict[str, Any]] = i18n_messages['messages']
        dict_message = more_itertools.first_true(messages, pred=lambda e: e["lang"] == locale.value)
        return dict_message['message']

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
        phrase = more_itertools.first_true(self.specs_inspection_phrases, lambda e: e['id'] == phrase_id)
        if phrase is None:
            return None

        return self.get_message(phrase['text'], locale)

    def get_label_name(self, label_id: str, locale: MessageLocale) -> Optional[str]:
        label = more_itertools.first_true(self.specs_labels, lambda e: e['label_id'] == label_id)
        if label is None:
            return None

        return self.get_message(label['label_name'], locale)

    def add_properties_to_inspection(self, inspection: Inspection,
                                     detail: Optional[Dict[str, Any]] = None) -> Inspection:
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

        commenter_account_id = inspection["commenter_account_id"]
        if commenter_account_id is not None:
            member = self.get_organization_member_from_account_id(commenter_account_id)
            inspection['commenter_user_id'] = member['user_id']
            inspection['commenter_username'] = member['username']
        else:
            inspection['commenter_user_id'] = None
            inspection['commenter_username'] = None

        inspection['phrase_names_en'] = [self.get_phrase_name(e, MessageLocale.EN) for e in inspection['phrases']]
        inspection['phrase_names_ja'] = [self.get_phrase_name(e, MessageLocale.JA) for e in inspection['phrases']]

        inspection['label_name_en'] = self.get_label_name(inspection['label_id'], MessageLocale.EN)
        inspection['label_name_ja'] = self.get_label_name(inspection['label_id'], MessageLocale.JA)

        if detail is not None:
            inspection.update(detail)

        return inspection
