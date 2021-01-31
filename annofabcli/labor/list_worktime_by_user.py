# pylint: disable=too-many-lines
import argparse
import calendar
import datetime
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import annofabapi
import more_itertools
import numpy
import pandas
from annofabapi.models import OrganizationMember, Project, ProjectMember
from annofabapi.utils import allow_404_error
from dataclasses_json import DataClassJsonMixin
from more_itertools import first_true

import annofabcli
from annofabcli import AnnofabApiFacade
from annofabcli.common.cli import AbstractCommandLineInterface, build_annofabapi_resource_and_login, get_list_from_args
from annofabcli.common.utils import isoduration_to_hour

logger = logging.getLogger(__name__)


def _create_required_columns(df: pandas.DataFrame, prior_columns: List[Any]) -> List[str]:
    remained_columns = list(df.columns.difference(prior_columns))
    all_columns = prior_columns + remained_columns
    return all_columns


def catch_exception(function: Callable[..., Any]) -> Callable[..., Any]:
    """
    Exceptionをキャッチしてログにstacktraceを出力する。
    """

    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(e)
            logger.exception(e)

    return wrapped


@dataclass(frozen=True)
class User(DataClassJsonMixin):
    account_id: str
    user_id: str
    username: str
    biography: Optional[str]


@dataclass(frozen=True)
class LaborWorktime(DataClassJsonMixin):
    """
    労務管理情報
    """

    date: str
    organization_id: str
    organization_name: str
    project_id: str
    project_title: str
    account_id: str
    user_id: str
    username: str
    biography: Optional[str]
    worktime_plan_hour: float
    """労務管理画面の予定作業時間"""
    worktime_result_hour: float
    """労務管理画面の実績作業時間"""
    worktime_monitored_hour: Optional[float]
    """AnnoFabの作業時間"""
    working_description: Optional[str]
    """実績作業時間に対する備考"""


@dataclass(frozen=True)
class LaborAvailability(DataClassJsonMixin):
    """
    労務管理情報
    """

    date: str
    account_id: str
    user_id: str
    username: str
    availability_hour: float


@dataclass(frozen=True)
class SumLaborWorktime(DataClassJsonMixin):
    """
    出力用の作業時間情報
    """

    date: str
    user_id: str
    worktime_plan_hour: float
    worktime_result_hour: float


class ListWorktimeByUserMain:
    def __init__(self, service: annofabapi.Resource):
        self.service = service
        self.facade = AnnofabApiFacade(service)

    DATE_FORMAT = "%Y-%m-%d"
    MONTH_FORMAT = "%Y-%m"

    _dict_account_statistics: Dict[str, List[Dict[str, Any]]] = {}
    """project_idごとの統計情報dict"""

    @allow_404_error
    def _get_account_statistics(self, project_id) -> Optional[List[Any]]:
        account_statistics = self.service.wrapper.get_account_statistics(project_id)
        return account_statistics

    def _get_worktime_monitored_hour_from_project_id(
        self, project_id: str, account_id: str, date: str
    ) -> Optional[float]:
        account_statistics = self._dict_account_statistics.get(project_id)
        if account_statistics is None:
            result = self._get_account_statistics(project_id)
            if result is not None:
                account_statistics = result
            else:
                logger.warning(f"project_id={project_id}: プロジェクトにアクセスできないため、アカウント統計情報を取得できませんでした。")
                account_statistics = []

            self._dict_account_statistics[project_id] = account_statistics

        return self._get_worktime_monitored_hour(account_statistics, account_id=account_id, date=date)

    @staticmethod
    def _get_worktime_monitored_hour(
        account_statistics: List[Dict[str, Any]], account_id: str, date: str
    ) -> Optional[float]:
        """
        AnnoFabの作業時間を取得する。
        """
        stat = first_true(account_statistics, pred=lambda e: e["account_id"] == account_id)
        if stat is None:
            return None
        histories = stat["histories"]
        hist = first_true(histories, pred=lambda e: e["date"] == date)
        if hist is None:
            return None
        return isoduration_to_hour(hist["worktime"])

    @staticmethod
    def create_required_columns(df, prior_columns):
        remained_columns = list(df.columns.difference(prior_columns))
        all_columns = prior_columns + remained_columns
        return all_columns

    @staticmethod
    def get_member_from_user_id(
        organization_member_list: List[OrganizationMember], user_id: str
    ) -> Optional[OrganizationMember]:
        member = more_itertools.first_true(organization_member_list, pred=lambda e: e["user_id"] == user_id)
        return member

    @staticmethod
    def get_project_title(project_list: List[Project], project_id: str) -> str:
        project = more_itertools.first_true(project_list, pred=lambda e: e["project_id"] == project_id)
        if project is not None:
            return project["title"]
        else:
            return ""

    @staticmethod
    def get_worktime_hour(working_time_by_user: Optional[Dict[str, Any]], key: str) -> float:
        if working_time_by_user is None:
            return 0

        value = working_time_by_user.get(key)
        if value is None:
            return 0
        else:
            return value / 3600 / 1000

    @staticmethod
    def _get_working_description(working_time_by_user: Optional[Dict[str, Any]]) -> Optional[str]:
        if working_time_by_user is None:
            return None

        return working_time_by_user.get("description")

    @staticmethod
    def _get_labor_worktime(
        labor: Dict[str, Any],
        member: Optional[ProjectMember],
        project_title: str,
        organization_name: str,
        worktime_monitored_hour: Optional[float],
    ) -> LaborWorktime:
        new_labor = LaborWorktime(
            date=labor["date"],
            organization_id=labor["organization_id"],
            organization_name=organization_name,
            project_id=labor["project_id"],
            project_title=project_title,
            account_id=labor["account_id"],
            user_id=member["user_id"] if member is not None else labor["account_id"],
            username=member["username"] if member is not None else labor["account_id"],
            biography=member["biography"] if member is not None else None,
            worktime_plan_hour=labor["plan_worktime"] if labor["plan_worktime"] is not None else 0,
            worktime_result_hour=labor["actual_worktime"] if labor["actual_worktime"] is not None else 0,
            working_description=labor["working_description"],
            worktime_monitored_hour=worktime_monitored_hour,
        )
        return new_labor

    def get_labor_availability_list_dict(
        self,
        user_list: List[User],
        start_date: str,
        end_date: str,
    ) -> Dict[str, List[LaborAvailability]]:
        """
        予定稼働時間を取得する
        Args:
            user_list:
            start_date:
            end_date:

        Returns:

        """
        labor_availability_dict = {}
        for user in user_list:
            # 予定稼働時間を取得するには、特殊な組織IDを渡す
            labor_list = self.service.wrapper.get_labor_control_availability(
                from_date=start_date,
                to_date=end_date,
                account_id=user.account_id,
            )
            new_labor_list = []
            for labor in labor_list:
                new_labor = LaborAvailability(
                    date=labor["date"],
                    account_id=labor["account_id"],
                    user_id=user.user_id,
                    username=user.username,
                    availability_hour=labor["availability"] if labor["availability"] is not None else 0,
                )
                new_labor_list.append(new_labor)
            labor_availability_dict[user.user_id] = new_labor_list
        return labor_availability_dict

    def get_labor_list_from_project_id(
        self,
        project_id: str,
        account_id_list: Optional[List[str]],
        start_date: Optional[str],
        end_date: Optional[str],
        add_monitored_worktime: bool = False,
    ) -> List[LaborWorktime]:
        organization, _ = self.service.api.get_organization_of_project(project_id)
        organization_name = organization["organization_name"]

        if account_id_list is None:
            logger.debug(f"project_id={project_id}の、すべての労務管理情報を取得しています。")
            labor_list = self.service.wrapper.get_labor_control_worktime(
                project_id=project_id,
                organization_id=organization["organization_id"],
                from_date=start_date,
                to_date=end_date,
            )
        else:
            labor_list = []
            for account_id in account_id_list:
                logger.debug(f"project_id={project_id}の、ユーザ{len(account_id_list)}件分の労務管理情報を取得しています。")
                tmp_labor_list = self.service.wrapper.get_labor_control_worktime(
                    project_id=project_id, from_date=start_date, to_date=end_date, account_id=account_id
                )
                labor_list.extend(tmp_labor_list)

        project_title = self.service.api.get_project(project_id)[0]["title"]
        labor_list = [
            e
            for e in labor_list
            if (e["actual_worktime"] is not None and e["actual_worktime"] > 0)
            or (e["plan_worktime"] is not None and e["plan_worktime"] > 0)
        ]
        logger.info(f"'{project_title}'プロジェクト('{project_id}')の労務管理情報の件数: {len(labor_list)}")

        new_labor_list = []
        for labor in labor_list:
            # 個人に紐付かないデータの場合
            if labor["account_id"] is None:
                continue

            member = self.facade.get_project_member_from_account_id(labor["project_id"], labor["account_id"])
            if add_monitored_worktime:
                try:
                    worktime_monitored_hour = self._get_worktime_monitored_hour_from_project_id(
                        project_id=project_id, account_id=labor["account_id"], date=labor["date"]
                    )
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"project_id={project_id}: 計測作業時間を取得できませんでした。", exc_info=True)
                    worktime_monitored_hour = None
            else:
                worktime_monitored_hour = None

            new_labor = self._get_labor_worktime(
                labor,
                member=member,
                project_title=project_title,
                organization_name=organization_name,
                worktime_monitored_hour=worktime_monitored_hour,
            )
            new_labor_list.append(new_labor)

        return new_labor_list

    def get_labor_list_from_organization_name(
        self,
        organization_name: str,
        account_id_list: Optional[List[str]],
        start_date: Optional[str],
        end_date: Optional[str],
        add_monitored_worktime: bool = False,
    ) -> List[LaborWorktime]:
        organization, _ = self.service.api.get_organization(organization_name)
        organization_id = organization["organization_id"]

        if account_id_list is None:
            logger.debug(f"organization_name={organization_name}の、すべての労務管理情報を取得しています。")
            labor_list = self.service.wrapper.get_labor_control_worktime(
                organization_id=organization_id, from_date=start_date, to_date=end_date
            )
        else:
            labor_list = []
            logger.debug(f"organization_name={organization_name}の、ユーザ{len(account_id_list)}件分の労務管理情報を取得しています。")
            for account_id in account_id_list:
                tmp_labor_list = self.service.wrapper.get_labor_control_worktime(
                    organization_id=organization_id, from_date=start_date, to_date=end_date, account_id=account_id
                )
                labor_list.extend(tmp_labor_list)

        labor_list = [
            e
            for e in labor_list
            if (e["actual_worktime"] is not None and e["actual_worktime"] > 0)
            or (e["plan_worktime"] is not None and e["plan_worktime"] > 0)
        ]

        logger.info(f"'{organization_name}'組織の労務管理情報の件数: {len(labor_list)}")
        project_list = self.service.wrapper.get_all_projects_of_organization(organization_name)

        new_labor_list = []
        for labor in labor_list:
            try:
                member = self.facade.get_project_member_from_account_id(labor["project_id"], labor["account_id"])
            except Exception:  # pylint: disable=broad-except
                logger.warning(f"project_id={labor['project_id']}: メンバ一覧を取得できませんでした。", exc_info=True)
                member = None

            project_title = self.get_project_title(project_list, labor["project_id"])
            if add_monitored_worktime:
                try:
                    worktime_monitored_hour = self._get_worktime_monitored_hour_from_project_id(
                        project_id=labor["project_id"], account_id=labor["account_id"], date=labor["date"]
                    )
                except Exception:  # pylint: disable=broad-except
                    logger.warning(f"project_id={labor['project_id']}: 計測作業時間を取得できませんでした。", exc_info=True)
                    worktime_monitored_hour = None
            else:
                worktime_monitored_hour = None

            new_labor = self._get_labor_worktime(
                labor,
                member=member,
                project_title=project_title,
                organization_name=organization_name,
                worktime_monitored_hour=worktime_monitored_hour,
            )
            new_labor_list.append(new_labor)

        return new_labor_list

    @staticmethod
    def get_sum_worktime_list(
        labor_list: List[LaborWorktime], user_id: str, start_date: str, end_date: str
    ) -> List[SumLaborWorktime]:
        sum_labor_list = []
        for date in pandas.date_range(start=start_date, end=end_date):
            str_date = date.strftime(ListWorktimeByUserMain.DATE_FORMAT)
            filtered_list = [e for e in labor_list if e.user_id == user_id and e.date == str_date]
            worktime_plan_hour = sum([e.worktime_plan_hour for e in filtered_list])
            worktime_result_hour = sum([e.worktime_result_hour for e in filtered_list])

            labor = SumLaborWorktime(
                user_id=user_id,
                date=date,
                worktime_plan_hour=worktime_plan_hour,
                worktime_result_hour=worktime_result_hour,
            )
            sum_labor_list.append(labor)

        return sum_labor_list

    @staticmethod
    @catch_exception
    def write_sum_worktime_list(sum_worktime_df: pandas.DataFrame, output_dir: Path):
        sum_worktime_df.round(3).to_csv(str(output_dir / "ユーザごとの作業時間.csv"), encoding="utf_8_sig", index=False)

    @staticmethod
    @catch_exception
    def write_sum_plan_worktime_list(sum_worktime_df: pandas.DataFrame, output_dir: Path) -> None:
        """
        出勤予定かどうかを判断するため、作業予定時間が"0"のときは"☓",　そうでないときは"○"で出力する
        Args:
            sum_worktime_df:
            output_dir:

        """

        def create_mark(value) -> str:
            if value == 0:
                return "×"
            else:
                return "○"

        def is_plan_column(c) -> bool:
            c1, c2 = c
            if c1 in ["date", "dayofweek"]:
                return False
            return c2 == "作業予定"

        username_list = [e[0] for e in sum_worktime_df.columns if is_plan_column(e)]

        for username in username_list:
            # SettingWithCopyWarning を避けるため、暫定的に値をコピーする
            sum_worktime_df[(username, "作業予定_記号")] = sum_worktime_df[(username, "作業予定")].map(create_mark)

        output_columns = [("date", ""), ("dayofweek", "")] + [(e, "作業予定_記号") for e in username_list]
        sum_worktime_df[output_columns].to_csv(str(output_dir / "ユーザごとの作業予定_記号.csv"), encoding="utf_8_sig", index=False)

    @staticmethod
    @catch_exception
    def write_worktime_list(worktime_df: pandas.DataFrame, output_dir: Path, add_monitored_worktime: bool = False):
        worktime_df = worktime_df.rename(
            columns={
                "worktime_plan_hour": "作業予定時間",
                "worktime_result_hour": "作業実績時間",
                "worktime_monitored_hour": "計測時間",
                "working_description": "備考",
            }
        )
        columns = [
            "date",
            "organization_name",
            "project_title",
            "project_id",
            "username",
            "biography",
            "user_id",
            "作業予定時間",
            "作業実績時間",
            "計測時間",
            "備考",
        ]
        if not add_monitored_worktime:
            columns.remove("計測時間")

        worktime_df[columns].round(3).to_csv(str(output_dir / "作業時間の詳細一覧.csv"), encoding="utf_8_sig", index=False)

    @staticmethod
    @catch_exception
    def write_worktime_per_user_date(worktime_df_per_date_user: pandas.DataFrame, output_dir: Path):
        add_availabaility = "availability_hour" in worktime_df_per_date_user.columns
        target_renamed_columns = {"worktime_plan_hour": "作業予定時間", "worktime_result_hour": "作業実績時間"}
        if add_availabaility:
            target_renamed_columns.update({"availability_hour": "予定稼働時間"})

        df = worktime_df_per_date_user.rename(columns=target_renamed_columns)
        columns = [
            "date",
            "user_id",
            "username",
            "biography",
            "予定稼働時間",
            "作業予定時間",
            "作業実績時間",
        ]
        if not add_availabaility:
            columns.remove("予定稼働時間")

        df[columns].round(3).to_csv(str(output_dir / "日ごとの作業時間の一覧.csv"), encoding="utf_8_sig", index=False)

    @staticmethod
    @catch_exception
    def write_worktime_per_user(worktime_df_per_user: pandas.DataFrame, output_dir: Path, add_availability: bool):
        target_renamed_columns = {
            "worktime_plan_hour": "作業予定時間",
            "worktime_result_hour": "作業実績時間",
            "result_working_days": "実績稼働日数",
        }
        if add_availability:
            target_renamed_columns.update({"availability_hour": "予定稼働時間"})
            target_renamed_columns.update({"availability_days": "予定稼働日数"})

        df = worktime_df_per_user.rename(columns=target_renamed_columns)
        columns = [
            "user_id",
            "username",
            "biography",
            "予定稼働時間",
            "作業予定時間",
            "作業実績時間",
            "予定稼働日数",
            "実績稼働日数",
        ]
        if not add_availability:
            columns.remove("予定稼働時間")
            columns.remove("予定稼働日数")

        df[columns].round(3).to_csv(str(output_dir / "summary.csv"), encoding="utf_8_sig", index=False)

    def get_organization_member_list(
        self, organization_name_list: Optional[List[str]], project_id_list: Optional[List[str]]
    ) -> List[OrganizationMember]:
        member_list: List[OrganizationMember] = []

        if project_id_list is not None:
            tmp_organization_name_list = []
            for project_id in project_id_list:
                organization, _ = self.service.api.get_organization_of_project(project_id)
                tmp_organization_name_list.append(organization["organization_name"])

            organization_name_list = list(set(tmp_organization_name_list))

        if organization_name_list is not None:
            for organization_name in organization_name_list:
                member_list.extend(self.service.wrapper.get_all_organization_members(organization_name))

        return member_list

    def _get_user_from_organization_name_list(self, organization_name_list: List[str], user_id: str) -> Optional[User]:
        for organization_name in organization_name_list:
            organization_member = self.service.wrapper.get_organization_member_or_none(organization_name, user_id)
            if organization_member is not None:
                return User(
                    user_id=organization_member["user_id"],
                    account_id=organization_member["account_id"],
                    username=organization_member["username"],
                    biography=organization_member["biography"],
                )
        return None

    def _get_user_from_project_id_list(self, project_id_list: List[str], user_id: str) -> Optional[User]:
        for project_id in project_id_list:
            project_member = self.service.wrapper.get_project_member_or_none(project_id, user_id)
            if project_member is not None:
                return User(
                    user_id=project_member["user_id"],
                    account_id=project_member["account_id"],
                    username=project_member["username"],
                    biography=project_member["biography"],
                )
        return None

    def get_user_list(
        self,
        labor_list: List[LaborWorktime],
        organization_name_list: Optional[List[str]] = None,
        project_id_list: Optional[List[str]] = None,
        user_id_list: Optional[List[str]] = None,
    ) -> List[User]:
        """
        summary.csvに出力するユーザ一覧を取得する。

        Args:
            labor_list:
            organization_name_list:
            project_id_list:
            user_id_list:

        Returns:
            ユーザ一覧

        """
        df = (
            pandas.DataFrame(labor_list, columns=["account_id", "user_id", "username", "biography"])
            .drop_duplicates()
            .set_index("user_id")
        )

        user_list: List[User] = []

        if user_id_list is None:
            for user_id, row in df.iterrows():
                user_list.append(
                    User(
                        user_id=str(user_id),
                        account_id=row["account_id"],
                        username=row["username"],
                        biography=row["biography"],
                    )
                )
            return user_list

        if organization_name_list is not None:
            for user_id in user_id_list:
                if user_id in df.index:
                    row = df.loc[user_id]
                    user_list.append(
                        User(
                            user_id=str(user_id),
                            account_id=row["account_id"],
                            username=row["username"],
                            biography=row["biography"],
                        )
                    )
                    continue

                user = self._get_user_from_organization_name_list(organization_name_list, user_id)
                if user is not None:
                    user_list.append(user)
                else:
                    logger.warning(f"user_id={user_id} のユーザは、組織メンバに存在しませんでした。")

        if project_id_list is not None:
            for user_id in user_id_list:
                if user_id in df.index:
                    row = df.loc[user_id]
                    user_list.append(
                        User(
                            user_id=str(user_id),
                            account_id=row["account_id"],
                            username=row["username"],
                            biography=row["biography"],
                        )
                    )
                    continue

                user = self._get_user_from_project_id_list(project_id_list, user_id)
                if user is not None:
                    user_list.append(user)
                else:
                    logger.warning(f"user_id={user_id} のユーザは、プロジェクトメンバに存在しませんでした。")

        return user_list

    @staticmethod
    def get_availability_list(
        labor_availability_list: List[LaborAvailability],
        start_date: str,
        end_date: str,
    ) -> List[Optional[float]]:
        def get_availability_hour(str_date: str) -> Optional[float]:
            labor = more_itertools.first_true(labor_availability_list, pred=lambda e: e.date == str_date)
            if labor is not None:
                return labor.availability_hour
            else:
                return None

        availability_list: List[Optional[float]] = []
        for date in pandas.date_range(start=start_date, end=end_date):
            str_date = date.strftime(ListWorktimeByUserMain.DATE_FORMAT)
            availability_list.append(get_availability_hour(str_date))

        return availability_list

    def get_account_id_list_from_project_id(self, user_id_list: List[str], project_id_list: List[str]) -> List[str]:
        """
        project_idのリストから、対象ユーザのaccount_id を取得する。

        Args:
            user_id_list:
            organization_name_list:

        Returns:
            account_idのリスト
        """
        account_id_list = []
        not_exists_user_id_list = []
        for user_id in user_id_list:
            member_exists = False
            for project_id in project_id_list:
                member = self.facade.get_project_member_from_user_id(project_id, user_id)
                if member is not None:
                    account_id_list.append(member["account_id"])
                    member_exists = True
                    break
            if not member_exists:
                not_exists_user_id_list.append(user_id)

        if len(not_exists_user_id_list) == 0:
            return account_id_list
        else:
            raise ValueError(f"以下のユーザは、指定されたプロジェクトのプロジェクトメンバではありませんでした。\n{not_exists_user_id_list}")

    def get_account_id_list_from_organization_name(
        self, user_id_list: List[str], organization_name_list: List[str]
    ) -> List[str]:
        """
        組織名のリストから、対象ユーザのaccount_id を取得する。

        Args:
            user_id_list:
            organization_name_list:

        Returns:
            account_idのリスト
        """

        def _get_account_id(fuser_id: str) -> Optional[str]:
            # 脱退した可能性のあるユーザの組織メンバ情報を取得する
            for organization_name in organization_name_list:
                member = self.service.wrapper.get_organization_member_or_none(organization_name, fuser_id)
                if member is not None:
                    return member["account_id"]
            return None

        # 組織メンバの一覧をする（ただし脱退したメンバは取得できない）
        all_organization_member_list = []
        for organization_name in organization_name_list:
            all_organization_member_list.extend(self.service.wrapper.get_all_organization_members(organization_name))

        user_id_dict = {e["user_id"]: e["account_id"] for e in all_organization_member_list}
        account_id_list = []
        not_exists_user_id_list = []
        for user_id in user_id_list:
            if user_id in user_id_dict:
                account_id_list.append(user_id_dict[user_id])
            else:
                account_id = _get_account_id(user_id)
                if account_id is not None:
                    account_id_list.append(account_id)
                else:
                    not_exists_user_id_list.append(user_id)

        if len(not_exists_user_id_list) == 0:
            return account_id_list
        else:
            raise ValueError(f"以下のユーザは、指定された組織の組織メンバではありませんでした。\n{not_exists_user_id_list}")

    def get_labor_list(
        self,
        organization_name_list: Optional[List[str]],
        project_id_list: Optional[List[str]],
        user_id_list: Optional[List[str]],
        start_date: Optional[str],
        end_date: Optional[str],
        add_monitored_worktime: bool = False,
    ) -> List[LaborWorktime]:

        labor_list: List[LaborWorktime] = []
        account_id_list: Optional[List[str]] = None

        logger.info(f"労務管理情報を取得します。")
        if project_id_list is not None:
            if user_id_list is not None:
                account_id_list = self.get_account_id_list_from_project_id(
                    user_id_list, project_id_list=project_id_list
                )

            for project_id in project_id_list:
                labor_list.extend(
                    self.get_labor_list_from_project_id(
                        project_id,
                        account_id_list=account_id_list,
                        start_date=start_date,
                        end_date=end_date,
                        add_monitored_worktime=add_monitored_worktime,
                    )
                )

        elif organization_name_list is not None:
            if user_id_list is not None:
                account_id_list = self.get_account_id_list_from_organization_name(
                    user_id_list, organization_name_list=organization_name_list
                )
            for organization_name in organization_name_list:
                labor_list.extend(
                    self.get_labor_list_from_organization_name(
                        organization_name,
                        account_id_list=account_id_list,
                        start_date=start_date,
                        end_date=end_date,
                        add_monitored_worktime=add_monitored_worktime,
                    )
                )

        else:
            raise RuntimeError(f"organization_name_list or project_id_list を指定してください。")

        # 集計対象ユーザで絞り込む
        if user_id_list is not None:
            return [e for e in labor_list if e.user_id in user_id_list]
        else:
            return labor_list

    @staticmethod
    def create_sum_worktime_df(
        labor_list: List[LaborWorktime],
        user_list: List[User],
        start_date: str,
        end_date: str,
        labor_availability_list_dict: Optional[Dict[str, List[LaborAvailability]]] = None,
    ):
        reform_dict = {
            ("date", ""): [
                e.strftime(ListWorktimeByUserMain.DATE_FORMAT)
                for e in pandas.date_range(start=start_date, end=end_date)
            ],
            ("dayofweek", ""): [e.strftime("%a") for e in pandas.date_range(start=start_date, end=end_date)],
        }

        username_list = []
        for user in user_list:
            sum_worktime_list = ListWorktimeByUserMain.get_sum_worktime_list(
                labor_list, user_id=user.user_id, start_date=start_date, end_date=end_date
            )

            username_list.append(user.username)
            reform_dict.update(
                {
                    (user.username, "作業予定"): [e.worktime_plan_hour for e in sum_worktime_list],
                    (user.username, "作業実績"): [e.worktime_result_hour for e in sum_worktime_list],
                }
            )

            if labor_availability_list_dict is not None:
                labor_availability_list = labor_availability_list_dict.get(user.user_id, [])
                reform_dict.update(
                    {
                        (user.username, "予定稼働"): ListWorktimeByUserMain.get_availability_list(
                            labor_availability_list, start_date, end_date
                        )
                    }
                )

        key_list = ["作業予定", "作業実績", "予定稼働"] if labor_availability_list_dict else ["作業予定", "作業実績"]
        for key in key_list:
            data = numpy.array([reform_dict[(username, key)] for username in username_list], dtype=float)
            data = numpy.nan_to_num(data)
            reform_dict[("合計", key)] = list(numpy.sum(data, axis=0))  # type: ignore

        columns = (
            [("date", ""), ("dayofweek", "")]
            + [("合計", key) for key in key_list]
            + [(username, key) for username in username_list for key in key_list]
        )

        sum_worktime_df = pandas.DataFrame(reform_dict, columns=columns)
        return sum_worktime_df

    @staticmethod
    def create_worktime_df_per_date_user(
        worktime_df: pandas.DataFrame,
        user_df: pandas.DataFrame,
        labor_availability_list_dict: Optional[Dict[str, List[LaborAvailability]]] = None,
    ) -> pandas.DataFrame:
        value_df = (
            worktime_df.pivot_table(
                values=["worktime_plan_hour", "worktime_result_hour"], index=["date", "user_id"], aggfunc=numpy.sum
            )
            .fillna(0)
            .reset_index()
        )
        if len(value_df) == 0:
            value_df = pandas.DataFrame(columns=["date", "user_id", "worktime_plan_hour", "worktime_result_hour"])

        if labor_availability_list_dict is not None:
            all_availability_list = []
            for availability_list in labor_availability_list_dict.values():
                all_availability_list.extend(availability_list)

            if len(all_availability_list) > 0:
                availability_df = pandas.DataFrame([e.to_dict() for e in all_availability_list])
            else:
                availability_df = pandas.DataFrame(columns=["date", "user_id", "availability_hour"])

            value_df = (
                value_df.merge(
                    availability_df[["date", "user_id", "availability_hour"]], how="outer", on=["date", "user_id"]
                )
                .fillna(0)
                .reset_index()
            )

        if len(value_df) > 0:
            return user_df.reset_index().merge(value_df, how="left", on=["user_id"]).reset_index()
        else:
            return pandas.DataFrame()

    @staticmethod
    def set_day_count_to_dataframe(
        worktime_df_per_date_user: pandas.DataFrame, value_df: pandas.DataFrame, worktime_column: str, days_column: str
    ):
        df_filter = worktime_df_per_date_user[worktime_df_per_date_user[worktime_column] > 0]
        if len(df_filter) > 0:
            value_df[days_column] = (
                df_filter.pivot_table(index=["user_id"], values="worktime_result_hour", aggfunc="count")
                .fillna(0)
                .astype(pandas.Int64Dtype())
            )
        else:
            value_df[days_column] = 0

    @staticmethod
    def get_value_columns(columns: pandas.Series) -> pandas.Series:
        """
        ユーザ情報以外のcolumnsを取得する
        """
        return columns.drop(["user_id", "username", "biography"])

    @staticmethod
    def create_worktime_df_per_user(
        worktime_df_per_date_user: pandas.DataFrame, user_df: pandas.DataFrame, add_availability: bool = False
    ) -> pandas.DataFrame:
        if len(worktime_df_per_date_user) > 0:
            value_df = worktime_df_per_date_user.pivot_table(index=["user_id"], aggfunc=numpy.sum).fillna(0)
            ListWorktimeByUserMain.set_day_count_to_dataframe(
                worktime_df_per_date_user,
                value_df,
                worktime_column="worktime_result_hour",
                days_column="result_working_days",
            )
            ListWorktimeByUserMain.set_day_count_to_dataframe(
                worktime_df_per_date_user,
                value_df,
                worktime_column="worktime_plan_hour",
                days_column="plan_working_days",
            )

            if add_availability:
                ListWorktimeByUserMain.set_day_count_to_dataframe(
                    worktime_df_per_date_user,
                    value_df,
                    worktime_column="availability_hour",
                    days_column="availability_days",
                )
            value_df.fillna(0, inplace=True)

        else:
            columns = [
                "availability_hour",
                "worktime_plan_hour",
                "worktime_result_hour",
                "availability_days",
                "plan_working_days",
                "result_working_days",
            ]
            if not add_availability:
                columns.remove("availability_hour")
                columns.remove("availability_days")
            value_df = pandas.DataFrame(columns=columns)

        user_df.set_index("user_id", inplace=True)

        df = user_df.join(value_df, how="left").reset_index()
        value_columns = ListWorktimeByUserMain.get_value_columns(df.columns)
        df[value_columns] = df[value_columns].fillna(0)
        return df

    def write_labor_list(
        self,
        labor_list: List[LaborWorktime],
        user_list: List[User],
        start_date: str,
        end_date: str,
        output_dir: Path,
        labor_availability_list_dict: Optional[Dict[str, List[LaborAvailability]]] = None,
        add_monitored_worktime: bool = False,
    ):
        if len(labor_list) > 0:
            worktime_df = pandas.DataFrame([e.to_dict() for e in labor_list])
            self.write_worktime_list(worktime_df, output_dir, add_monitored_worktime)
        else:
            worktime_df = pandas.DataFrame(columns=["date", "user_id", "worktime_plan_hour", "worktime_result_hour"])
            logger.info("予定作業時間または実績作業時間が入力されているデータは見つからなかったので、'作業時間の詳細一覧.csv' は出力しません。")

        # 日ごとの作業時間の一覧.csv を出力
        user_df = pandas.DataFrame(user_list)
        worktime_df_per_date_user = self.create_worktime_df_per_date_user(
            worktime_df=worktime_df, user_df=user_df, labor_availability_list_dict=labor_availability_list_dict
        )
        if len(worktime_df_per_date_user) > 0:
            self.write_worktime_per_user_date(worktime_df_per_date_user, output_dir)
        else:
            logger.info("日ごとの作業時間情報に関するデータが見つからなかったので、 '日ごとの作業時間の一覧.csv' は出力しません。")

        add_availability = labor_availability_list_dict is not None
        worktime_df_per_user = self.create_worktime_df_per_user(
            worktime_df_per_date_user=worktime_df_per_date_user, user_df=user_df, add_availability=add_availability
        )
        self.write_worktime_per_user(worktime_df_per_user, output_dir, add_availability=add_availability)

        # 行方向に日付、列方向にユーザを表示したDataFrame
        sum_worktime_df = self.create_sum_worktime_df(
            labor_list=labor_list,
            user_list=user_list,
            start_date=start_date,
            end_date=end_date,
            labor_availability_list_dict=labor_availability_list_dict,
        )
        self.write_sum_worktime_list(sum_worktime_df, output_dir)
        self.write_sum_plan_worktime_list(sum_worktime_df, output_dir)

    def main(
        self,
        organization_name_list: Optional[List[str]],
        project_id_list: Optional[List[str]],
        user_id_list: Optional[List[str]],
        start_date: Optional[str],
        end_date: Optional[str],
        output_dir: Path,
        add_availability: bool = False,
        add_monitored_worktime: bool = False,
    ) -> None:
        """
        作業時間の一覧を出力する
        """
        labor_list = self.get_labor_list(
            organization_name_list=organization_name_list,
            project_id_list=project_id_list,
            user_id_list=user_id_list,
            start_date=start_date,
            end_date=end_date,
            add_monitored_worktime=add_monitored_worktime,
        )

        if len(labor_list) == 0:
            logger.info(f"予定/実績に関する労務管理情報が0件です。")
            if start_date is None or end_date is None or user_id_list is None:
                logger.info(f"後続の処理を続けることができないので終了します。")
                return

        if start_date is None or end_date is None:
            sorted_date_list = sorted({e.date for e in labor_list if e.worktime_result_hour > 0})
            if start_date is None:
                start_date = sorted_date_list[0]
            if end_date is None:
                end_date = sorted_date_list[-1]

        logger.info(f"集計期間: start_date={start_date}, end_date={end_date}")
        user_list = self.get_user_list(
            labor_list,
            organization_name_list=organization_name_list,
            project_id_list=project_id_list,
            user_id_list=user_id_list,
        )
        logger.info(f"集計対象ユーザの数: {len(user_list)}")

        labor_availability_list_dict: Optional[Dict[str, List[LaborAvailability]]] = None
        if add_availability:
            labor_availability_list_dict = self.get_labor_availability_list_dict(
                user_list=user_list,
                start_date=start_date,
                end_date=end_date,
            )

        self.write_labor_list(
            labor_list=labor_list,
            user_list=user_list,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
            labor_availability_list_dict=labor_availability_list_dict,
            add_monitored_worktime=add_monitored_worktime,
        )

    def get_user_id_list_from_project_id_list(self, project_id_list: List[str]) -> List[str]:
        """
        プロジェクトメンバ一覧からuser_id_listを取得する。
        Args:
            project_id_list:

        Returns:
            user_id_list

        """
        member_list: List[Dict[str, Any]] = []
        for project_id in project_id_list:
            member_list.extend(self.service.wrapper.get_all_project_members(project_id))
        user_id_list = [e["user_id"] for e in member_list]
        return list(set(user_id_list))

    @staticmethod
    def get_first_and_last_date(str_month: str) -> Tuple[str, str]:
        """
        年月（"YYYY-MM"）から、月初と月末の日付を返す。

        Args:
            str_month: 年月（"YYYY-MM"）

        Returns:
            月初と月末の日付が格納されたタプル

        """
        dt_first_date = datetime.datetime.strptime(str_month, ListWorktimeByUserMain.MONTH_FORMAT)
        _, days = calendar.monthrange(dt_first_date.year, dt_first_date.month)
        dt_last_date = dt_first_date + datetime.timedelta(days=(days - 1))
        return (
            dt_first_date.strftime(ListWorktimeByUserMain.DATE_FORMAT),
            dt_last_date.strftime(ListWorktimeByUserMain.DATE_FORMAT),
        )

    @staticmethod
    def get_start_and_end_date_from_month(start_month: str, end_month: str) -> Tuple[str, str]:
        """
        開始月、終了月から、開始日付、終了日付を取得する。

        Args:
            start_month:
            end_month:

        Returns:


        """
        first_date, _ = ListWorktimeByUserMain.get_first_and_last_date(start_month)
        _, end_date = ListWorktimeByUserMain.get_first_and_last_date(end_month)
        return first_date, end_date


class ListWorktimeByUser(AbstractCommandLineInterface):
    """
    作業時間をユーザごとに出力する。
    """

    @staticmethod
    def get_start_and_end_date_from_args(args: argparse.Namespace) -> Tuple[Optional[str], Optional[str]]:
        if args.start_date is not None:
            start_date = args.start_date
        elif args.start_month is not None:
            start_date, _ = ListWorktimeByUserMain.get_first_and_last_date(args.start_month)
        else:
            start_date = None

        if args.end_date is not None:
            end_date = args.end_date
        elif args.end_month is not None:
            _, end_date = ListWorktimeByUserMain.get_first_and_last_date(args.end_month)
        else:
            end_date = None

        return (start_date, end_date)

    def main(self) -> None:
        args = self.args

        arg_user_id_list = get_list_from_args(args.user_id) if args.user_id is not None else None
        project_id_list = get_list_from_args(args.project_id) if args.project_id is not None else None
        organization_name_list = get_list_from_args(args.organization) if args.organization is not None else None

        start_date, end_date = self.get_start_and_end_date_from_args(args)
        output_dir = Path(args.output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)

        mian_obj = ListWorktimeByUserMain(self.service)
        mian_obj.main(
            organization_name_list=organization_name_list,
            project_id_list=project_id_list,
            start_date=start_date,
            end_date=end_date,
            output_dir=output_dir,
            user_id_list=arg_user_id_list,
            add_availability=args.add_availability,
            add_monitored_worktime=args.add_monitored_worktime,
        )


def main(args):
    service = build_annofabapi_resource_and_login(args)
    facade = AnnofabApiFacade(service)
    ListWorktimeByUser(service, facade, args).main()


def parse_args(parser: argparse.ArgumentParser):
    target_group = parser.add_mutually_exclusive_group(required=True)
    target_group.add_argument(
        "-org",
        "--organization",
        type=str,
        nargs="+",
        help="集計対象の組織名を指定してください。`file://`を先頭に付けると、組織名の一覧が記載されたファイルを指定できます。",
    )

    target_group.add_argument(
        "-p",
        "--project_id",
        type=str,
        nargs="+",
        help="集計対象のプロジェクトを指定してください。`file://`を先頭に付けると、project_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument(
        "-u",
        "--user_id",
        type=str,
        nargs="+",
        help="集計対象のユーザのuser_idを指定してください。`--organization`を指定した場合は必須です。"
        "指定しない場合は、プロジェクトメンバが指定されます。"
        "`file://`を先頭に付けると、user_idの一覧が記載されたファイルを指定できます。",
    )

    parser.add_argument("--add_availability", action="store_true", help="指定した場合、'ユーザごとの作業時間.csv'に予定稼働時間も出力します。")
    parser.add_argument(
        "--add_monitored_worktime", action="store_true", help="指定した場合、'作業時間の詳細一覧.csv'にAnnoFab計測時間も出力します。"
    )

    start_period_group = parser.add_mutually_exclusive_group()
    start_period_group.add_argument("--start_date", type=str, help="集計期間の開始日(YYYY-MM-DD)")
    start_period_group.add_argument("--start_month", type=str, help="集計期間の開始月(YYYY-MM-DD)")

    end_period_group = parser.add_mutually_exclusive_group()
    end_period_group.add_argument("--end_date", type=str, help="集計期間の終了日(YYYY-MM)")
    end_period_group.add_argument("--end_month", type=str, help="集計期間の終了月(YYYY-MM)")

    parser.add_argument("-o", "--output_dir", type=str, required=True, help="出力先のディレクトリのパス")

    parser.set_defaults(subcommand_func=main)


def add_parser(subparsers: argparse._SubParsersAction):
    subcommand_name = "list_worktime_by_user"
    subcommand_help = "ユーザごとに作業予定時間、作業実績時間を出力します。"
    description = "ユーザごとに作業予定時間、作業実績時間を出力します。"

    parser = annofabcli.common.cli.add_parser(subparsers, subcommand_name, subcommand_help, description)
    parse_args(parser)
