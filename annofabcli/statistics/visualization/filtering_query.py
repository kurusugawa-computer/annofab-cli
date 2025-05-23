from __future__ import annotations

import logging
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any, Optional

from annofabapi.dataclass.task import Task as DcTask
from annofabapi.models import Task

from annofabcli.common.facade import TaskQuery, match_task_with_query
from annofabcli.common.utils import isoduration_to_hour

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FilteringQuery:
    """
    絞り込み条件
    """

    task_query: Optional[TaskQuery] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    ignored_task_ids: Optional[Collection[str]] = None


def _get_first_annotation_started_datetime(sub_task_history_list: list[dict[str, Any]]) -> Optional[str]:
    """
    1個のタスクのタスク履歴一覧から、最初に教師付フェーズを作業した日時を取得します。
    """
    task_history_list_with_annotation_phase = [
        e for e in sub_task_history_list if e["phase"] == "annotation" and e["account_id"] is not None and isoduration_to_hour(e["accumulated_labor_time_milliseconds"]) > 0
    ]
    if len(task_history_list_with_annotation_phase) == 0:
        return None

    return task_history_list_with_annotation_phase[0]["started_datetime"]


def filter_task_histories(task_histories: dict[str, list[dict[str, Any]]], *, start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict[str, list[dict[str, Any]]]:
    """
    タスク履歴を絞り込みます。

    Args:
        task_histories: タスク履歴情報。key:task_id, value:タスク履歴一覧
        start_date: `作業開始日 >= start_date`という条件を指定します。
        end_date: `作業開始日 <= end_date`という条件を指定します。

    Returns:
        タスク一覧

    """
    if start_date is None and end_date is None:
        return task_histories

    def pred(sub_task_history_list: list[dict[str, Any]]) -> bool:
        first_annotation_started_datetime = _get_first_annotation_started_datetime(sub_task_history_list)
        if first_annotation_started_datetime is None:
            return False

        first_annotation_started_date = first_annotation_started_datetime[0:10]
        result = True
        if start_date is not None:
            result = result and (first_annotation_started_date >= start_date)
        if end_date is not None:
            result = result and (first_annotation_started_date <= end_date)

        return result

    return {task_id: sub_task_history_list for task_id, sub_task_history_list in task_histories.items() if pred(sub_task_history_list)}


def filter_tasks(tasks: list[dict[str, Any]], query: FilteringQuery, *, task_histories: dict[str, list[dict[str, Any]]]) -> list[Task]:
    """
    タスク一覧を絞り込みます。

    Args:
        tasks: タスク一覧
        query: 絞り込み条件
        task_histories: タスク履歴情報。`query.start_date`, `query.end_date`で絞り込む際に利用します。

    Returns:
        絞り込み後のタスク一覧

    """

    def _filter_with_task_query(arg_task: dict[str, Any]) -> bool:
        """
        検索条件にマッチするかどうか

        Returns:
            Trueを返すなら検索条件にマッチする
        """

        flag = True
        if query.task_query is not None:
            flag = flag and match_task_with_query(DcTask.from_dict(arg_task), query.task_query)

        if query.ignored_task_ids is not None:
            flag = flag and arg_task["task_id"] not in query.ignored_task_ids

        return flag

    filtered_tasks = [task for task in tasks if _filter_with_task_query(task)]

    # タスク履歴で絞り込む理由：
    # `start_date`,`end_date`は教師付開始日で絞り込む。教師付開始日はタスク履歴からしか算出できないため
    filtered_task_histories = filter_task_histories(task_histories, start_date=query.start_date, end_date=query.end_date)
    result = [task for task in filtered_tasks if task["task_id"] in filtered_task_histories]
    return result
