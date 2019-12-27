# flake8: noqa
#  type: ignore
# pylint: skip-file
from datetime import date, timedelta
from typing import Any, Dict


def date_range(start_date: date, end_date: date):
    diff = (end_date - start_date).days + 1
    return (start_date + timedelta(i) for i in range(diff))


def print_time_list_from_work_time_list(username_list: list, work_time_lists: list, date_list: list):
    print_time_list = []
    new_header_name_list = []
    new_header_item_list = []
    new_footer_item_list = []
    new_header_name_list.append("")
    new_header_item_list.append("date / time")
    new_footer_item_list.append("total_time")
    username_footer_list: Dict[str, Any] = {}
    total_aw_plans = 0.0
    total_aw_results = 0.0
    total_af_time = 0.0

    for username in username_list:
        new_header_name_list.append(username)
        new_header_name_list.append("")
        new_header_name_list.append("")
        new_header_name_list.append("")
        new_header_name_list.append("")
        new_header_item_list.append("aw_plans")
        new_header_item_list.append("aw_results")
        new_header_item_list.append("af_time")
        new_header_item_list.append("diff")
        new_header_item_list.append("diff_per")
        username_footer_list[username] = {}
        username_footer_list[username]["aw_plans"] = 0.0
        username_footer_list[username]["aw_results"] = 0.0
        username_footer_list[username]["af_time"] = 0.0

    print_time_list.append(new_header_name_list)
    print_time_list.append(new_header_item_list)

    for day in date_list:
        new_line = []
        new_line.append(day.strftime("%Y-%m-%d"))
        for username in username_list:
            aw_plans = 0.0
            aw_results = 0.0
            af_time = 0.0

            for work_time_list in work_time_lists:
                for work_time in work_time_list:
                    if username == work_time["username"] and day.strftime("%Y-%m-%d") == work_time["date"]:
                        aw_plans += work_time["aw_plans"]
                        aw_results += work_time["aw_results"]
                        af_time += work_time["af_time"]

            new_line.append(round(aw_plans, 2))
            new_line.append(round(aw_results, 2))
            new_line.append(round(af_time, 2))
            diff = round(aw_results - af_time, 2)
            diff_per = round(diff / aw_results, 2) if aw_results != 0.0 else 0.0
            new_line.append(diff)
            new_line.append(diff_per)
            username_footer_list[username]["aw_plans"] += aw_plans
            username_footer_list[username]["aw_results"] += aw_results
            username_footer_list[username]["af_time"] += af_time

        print_time_list.append(new_line)

    for username in username_list:
        new_footer_item_list.append(round(username_footer_list[username]["aw_plans"], 2))
        total_aw_plans += username_footer_list[username]["aw_plans"]
        new_footer_item_list.append(round(username_footer_list[username]["aw_results"], 2))
        total_aw_results += username_footer_list[username]["aw_results"]
        new_footer_item_list.append(round(username_footer_list[username]["af_time"], 2))
        total_af_time += username_footer_list[username]["af_time"]
        total_diff = round(username_footer_list[username]["aw_results"] - username_footer_list[username]["af_time"], 2)
        total_diff_per = (
            round(total_diff / username_footer_list[username]["aw_results"], 2)
            if (username_footer_list[username]["aw_results"] != 0.0)
            else 0.0
        )
        new_footer_item_list.append(total_diff)
        new_footer_item_list.append(total_diff_per)

    print_time_list.append(new_footer_item_list)

    return (
        print_time_list,
        {
            "total_aw_results": round(total_aw_results, 2),
            "total_aw_plans": round(total_aw_plans, 2),
            "total_af_time": round(total_af_time, 2),
            "total_diff": round(total_aw_results - total_af_time, 2),
            "total_diff_per": (
                round((total_aw_results - total_af_time) / total_aw_results, 2) if (total_aw_results != 0.00) else 0.00
            ),
        },
    )


def print_time_list_csv(print_time_list: list) -> None:
    for time_list in print_time_list:
        print(*time_list, sep=",")
