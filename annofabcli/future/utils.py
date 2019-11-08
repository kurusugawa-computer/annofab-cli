from datetime import date, datetime, timedelta
from typing import Optional


def account_id_to_user_id(project_members: dict, account_id: str) -> str:
    """

    :param project_members:
    :param member_task_aggregate:
    :return:
    """

    # member_task_aggregateにuser_idを追加する
    def _to_user_id(project_members: dict, account_id: str) -> Optional[str]:
        for member_details in project_members["list"]:
            if member_details["account_id"] == account_id:
                return member_details["user_id"]
        return

    user_id = _to_user_id(project_members, account_id)

    return user_id if user_id != None else account_id


def date_range(start_date: date, end_date: date):
    diff = (end_date - start_date).days + 1
    return (start_date + timedelta(i) for i in range(diff))


def work_time_list_to_print_time_list(project_members: dict, work_time_list: list, date_list: list):
    print_time_list = []
    new_header_name_list = []
    new_header_item_list = []
    new_footer_item_list = []
    new_header_name_list.append("")
    new_header_item_list.append("date / time")
    new_footer_item_list.append("total_time")
    for work_time in work_time_list:
        new_header_name_list.append(account_id_to_user_id(project_members, work_time["account_id"]))
        new_header_name_list.append("")
        new_header_name_list.append("")
        new_header_name_list.append("")
        new_header_item_list.append("annowork_plans")
        new_header_item_list.append("annowork")
        new_header_item_list.append("annofab")
        new_header_item_list.append("difference")
        new_footer_item_list.append(work_time["total_time"]["annowork_plans_time"])
        new_footer_item_list.append(work_time["total_time"]["annowork_time"])
        new_footer_item_list.append(work_time["total_time"]["worktime"])
        new_footer_item_list.append(work_time["total_time"]["annowork_time"] - work_time["total_time"]["worktime"])

    print_time_list.append(new_header_name_list)
    print_time_list.append(new_header_item_list)

    for date in date_list:
        new_line = []
        new_line.append(date.strftime("%Y-%m-%d"))
        for work_time in work_time_list:
            flag = False
            for history in work_time["histories"]:
                if date == datetime.strptime(history["date"], '%Y-%m-%d').date():
                    flag = True
                    new_line.append(history["annowork_plans_time"])
                    new_line.append(history["annowork_time"])
                    new_line.append(history["worktime"])
                    new_line.append(round(history["annowork_time"] - history["worktime"], 2))
                    break
            if flag == False:
                new_line.append("0.0")
                new_line.append("0.0")
                new_line.append("0.0")
                new_line.append("0.0")

        print_time_list.append(new_line)
    print_time_list.append(new_footer_item_list)

    return print_time_list

def work_time_lists_to_print_time_list(project_members: dict, work_time_lists: list, date_list: list):
    print_time_list = []
    new_header_name_list = []
    new_header_item_list = []
    new_footer_item_list = []
    new_header_name_list.append("")
    new_header_item_list.append("date / time")
    new_footer_item_list.append("total_time")
    account_id_list = []


    for work_time_list in work_time_lists:
        for work_time in work_time_list:
            if not account_id_to_user_id(project_members, work_time["account_id"]) in new_header_name_list:
                account_id_list.append(work_time["account_id"])
                new_header_name_list.append(account_id_to_user_id(project_members, work_time["account_id"]))
                new_header_name_list.append("")
                new_header_name_list.append("")
                new_header_name_list.append("")
                new_header_item_list.append("annowork_plans")
                new_header_item_list.append("annowork")
                new_header_item_list.append("annofab")
                new_header_item_list.append("difference")


    for account_id in account_id_list:
        footer_annowork_plans_time = 0.0
        footer_annowork_time = 0.0
        footer_worktime = 0.0
        for work_time_list in work_time_lists:
            for work_time in work_time_list:
                if work_time["account_id"] == account_id:
                    footer_annowork_plans_time += float(work_time["total_time"]["annowork_plans_time"])
                    footer_annowork_time += float(work_time["total_time"]["annowork_time"])
                    footer_worktime += float(work_time["total_time"]["worktime"])
        new_footer_item_list.append(footer_annowork_plans_time)
        new_footer_item_list.append(footer_annowork_time)
        new_footer_item_list.append(footer_worktime)
        new_footer_item_list.append(
            footer_annowork_time - footer_worktime)


    print_time_list.append(new_header_name_list)
    print_time_list.append(new_header_item_list)

    for date in date_list:
        new_line = []
        new_line.append(date.strftime("%Y-%m-%d"))
        for account_id in account_id_list:
            annowork_plans_time = 0.0
            annowork_time = 0.0
            worktime = 0.0
            diff_time = 0.0

            for work_time_list in work_time_lists:
                for work_time in work_time_list:
                    if account_id == work_time["account_id"]:
                        for history in work_time["histories"]:
                            if date == datetime.strptime(history["date"], '%Y-%m-%d').date():
                                annowork_plans_time += history["annowork_plans_time"]
                                annowork_time += history["annowork_time"]
                                worktime += history["worktime"]
                                diff_time = round(annowork_time - worktime, 2)

            new_line.append(annowork_plans_time)
            new_line.append(annowork_time)
            new_line.append(worktime)
            new_line.append(diff_time)
        print_time_list.append(new_line)
    print_time_list.append(new_footer_item_list)

    return print_time_list


def print_time_list_csv(print_time_list: list) -> None:
    for time_list in print_time_list:
        print(*time_list, sep=",")
