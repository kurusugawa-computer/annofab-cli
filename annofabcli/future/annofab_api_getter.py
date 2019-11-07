import datetime
from datetime import date
import logging
from annofabcli.common.utils import isoduration_to_minute

###################
###生のAPIを叩くやつ
###################

logger = logging.getLogger(__name__)

class AnnofabGetter:
    def __init__(self, service, project_id: str, organization_id: str):
        self.service = service
        self.project_id = project_id
        self.organization_id = organization_id

    def get_tasks(self, page_no: int = 1) -> dict:
        # クライアントのインスタンスを生成します。
        tasks = self.service.api.get_tasks(project_id=self.project_id, query_params={"page": page_no})
        return tasks[0]

    def get_account_statistics(self) -> list:
        account_statistics = self.service.api.get_account_statistics(project_id=self.project_id)
        return account_statistics[0]

    def get_project_members(self) -> dict:
        project_members = self.service.api.get_project_members(project_id=self.project_id)
        return project_members[0]

    def get_labor_control(self, account_id: str = None, from_date: date = None, to_date: date = None):
        labor_control = self.service.api.get_labor_control({
            "organization_id": self.organization_id,
            "project_id": self.project_id,
            "account_id": account_id,
            "from": from_date.strftime("%Y-%m-%d"),
            "to": to_date.strftime("%Y-%m-%d")
        })
        return labor_control[0]

    def get_inspections(self, task_id: str = None, input_data_id: str = None):
        inspections = self.service.api.get_inspections(self.project_id, task_id, input_data_id)

        return inspections[0]


###################
###APIのWrapper
###################


def get_member_list(annofab_getter: AnnofabGetter):
    # user_idを羅列しただけのlistを返す
    def _project_members_to_list(project_members: dict) -> list:
        member_list = []
        for member_details in project_members["list"]:
            member_list.append(member_details["account_id"])
        return member_list

    project_members = annofab_getter.get_project_members()
    return _project_members_to_list(project_members)


def get_member_dict(annofab_getter: AnnofabGetter):
    # account_idを羅列しただけのlistを返す
    def _project_members_to_list(project_members: dict) -> dict:
        member_list = {}
        for member_details in project_members["list"]:
            member_list[member_details["account_id"]] = []
        return member_list

    project_members = annofab_getter.get_project_members()
    return _project_members_to_list(project_members)


def get_annowork_results_minute(annofab_getter: AnnofabGetter, account_id: str = None, start: date = None,
                                end: date = None):
    annowork_time = annofab_getter.get_labor_control(account_id, start, end)

    return annowork_time


def get_account_statistics_target_period(annofab_getter: AnnofabGetter, start: date = None, end: date = None):
    account_statistics_list = annofab_getter.get_account_statistics()
    new_account_statistics_list = []
    for account_statistics in account_statistics_list:
        new_account_statistics = []
        for date_statistics in account_statistics["histories"]:
            if start <= datetime.datetime.strptime(date_statistics["date"], '%Y-%m-%d').date() <= end:
                new_account_statistics.append(date_statistics)
        new_account_statistics_list.append({
            "account_id": account_statistics["account_id"],
            "histories": new_account_statistics
        })

    return new_account_statistics_list


def get_work_time_list(annofab_getter: AnnofabGetter, start_date: date = None, end_date: date = None):
    account_statistics_list = get_account_statistics_target_period(annofab_getter, start=start_date, end=end_date)
    logger.debug(f"len(account_statistics_list) = {len(account_statistics_list)}")

    for account_index, account_statistics in enumerate(account_statistics_list):
        logger.debug(f"{account_index} 件目: account_id = {account_statistics['account_id']}")
        total_worktime = 0.0
        total_annowork_time = 0.0
        total_annowork_plans_time = 0.0

        histories = account_statistics["histories"]
        logger.debug(f"len(histories) = {len(histories)}")
        for history_index, history in enumerate(histories):
            logger.debug(f"{history_index} 件目: date = {history['date']}")
            history_date = datetime.datetime.strptime(history["date"], '%Y-%m-%d').date()
            annowork_results_minute_list = get_annowork_results_minute(annofab_getter,
                                                                       account_id=account_statistics["account_id"],
                                                                       start=history_date, end=history_date)
            for annowork_results_minute in annowork_results_minute_list:
                if annowork_results_minute["date"] == history["date"]:
                    if annowork_results_minute["values"]["working_time_by_user"]["results"] != None:
                        history["worktime"] = round(isoduration_to_minute(history["worktime"]), 2)
                        total_worktime += float(history["worktime"])
                        history["annowork_time"] = round(
                            int(annowork_results_minute["values"]["working_time_by_user"]["results"]) / 60000, 2)
                        total_annowork_time += float(
                            int(annowork_results_minute["values"]["working_time_by_user"]["results"]) / 60000)
                        if annowork_results_minute["values"]["working_time_by_user"]["plans"] != None:
                            history["annowork_plans_time"] = round(
                                int(annowork_results_minute["values"]["working_time_by_user"]["plans"]) / 60000, 2)
                            total_annowork_plans_time += float(
                                int(annowork_results_minute["values"]["working_time_by_user"]["plans"]) / 60000)
                        else:
                            history["annowork_plans_time"] = 0.00
                    else:
                        history["worktime"] = round(isoduration_to_minute(history["worktime"]), 2)
                        total_worktime += float(history["worktime"])
                        history["annowork_time"] = 0.00
                        if annowork_results_minute["values"]["working_time_by_user"]["plans"] != None:
                            history["annowork_plans_time"] = round(
                                int(annowork_results_minute["values"]["working_time_by_user"]["plans"]) / 60000, 2)
                            total_annowork_plans_time += float(
                                int(annowork_results_minute["values"]["working_time_by_user"]["plans"]) / 60000)
                        else:
                            history["annowork_plans_time"] = 0.00

            if not "annowork_time" in history:
                history["worktime"] = round(isoduration_to_minute(history["worktime"]), 2)
                total_worktime += float(history["worktime"])
                history["annowork_time"] = 0.00
                if annowork_results_minute["values"]["working_time_by_user"]["plans"] != None:
                    history["annowork_plans_time"] = round(
                        int(annowork_results_minute["values"]["working_time_by_user"]["plans"]) / 60000, 2)
                    total_annowork_plans_time += float(
                        int(annowork_results_minute["values"]["working_time_by_user"]["plans"]) / 60000)
                else:
                    history["annowork_plans_time"] = 0.00

        account_statistics["total_time"] = {
            "worktime": total_worktime,
            "annowork_time": total_annowork_time,
            "annowork_plans_time": total_annowork_plans_time
        }

    return account_statistics_list
