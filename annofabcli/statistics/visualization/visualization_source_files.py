from __future__ import annotations

import json
import logging
from collections.abc import Collection
from pathlib import Path
from typing import Any

import annofabapi.utils

from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile
from annofabcli.common.exceptions import DownloadingFileNotFoundError

logger = logging.getLogger(__name__)


class VisualizationSourceFiles:
    """
    可視化に必要なファイルに関するクラス。

    このクラスで、可視化に必要なファイルの作成や読み込みができます。

    """

    def __init__(
        self,
        annofab_service: annofabapi.Resource,
        project_id: str,
        target_dir: Path,
    ) -> None:
        self.annofab_service = annofab_service
        self.project_id = project_id
        self.target_dir = target_dir

        # ダウンロードした一括情報
        self.task_json_path = self.target_dir / f"{self.project_id}__task.json"
        self.comment_json_path = target_dir / f"{self.project_id}__comment.json"
        self.task_history_json_path = target_dir / f"{self.project_id}__task-history.json"
        self.task_history_event_json_path = target_dir / f"{self.project_id}__task-history-event.json"
        self.annotation_zip_path = target_dir / f"{self.project_id}__annotation.zip"

        self.logging_prefix = f"project_id='{project_id}'"

    def download(self):  # noqa: ANN201
        pass

    def read_tasks_json(
        self,
    ) -> list[dict[str, Any]]:
        """
        タスク全件ファイルを読み込みます。

        Returns:
            全タスクのlist
        """
        with self.task_json_path.open(encoding="utf-8") as f:
            all_tasks = json.load(f)

        logger.debug(f"{self.logging_prefix}: '{self.task_json_path}'を読み込みました。{len(all_tasks)}件のタスクが含まれています。")
        return all_tasks

    def read_task_histories_json(self) -> dict[str, list[dict[str, Any]]]:
        """
        タスク履歴全件ファイルを読み込みます。

        Returns:
            全タスクの履歴情報。keyはtask_id, valueはタスク履歴のlist
        """
        with open(str(self.task_history_json_path), encoding="utf-8") as f:  # noqa: PTH123
            task_histories_dict = json.load(f)

        logger.debug(f"{self.logging_prefix}: '{self.task_history_json_path}'を読み込みました。{len(task_histories_dict)}件のタスクの履歴が含まれています。")
        return task_histories_dict

    def read_task_history_events_json(self) -> list[dict[str, Any]]:
        """
        タスク履歴イベント全件ファイルを読み込みます。

        Returns:
            全タスクの履歴イベント情報
        """
        with self.task_history_event_json_path.open(encoding="utf-8") as f:
            task_history_event_list = json.load(f)

        logger.debug(f"{self.logging_prefix}: '{self.task_history_event_json_path}'を読み込みました。{len(task_history_event_list)}件のタスク履歴イベントが含まれています。")
        return task_history_event_list

    def read_comments_json(self) -> list[dict[str, Any]]:
        """
        コメント全件ファイルを読み込みます。

        Returns:
            全コメントの一覧。検査コメントだけでなく保留コメントや、返信のコメントも含まれています。
        """
        with open(str(self.comment_json_path), encoding="utf-8") as f:  # noqa: PTH123
            comment_list = json.load(f)

        logger.debug(f"{self.logging_prefix}: '{self.comment_json_path}'を読み込みました。{len(comment_list)}件のコメントが含まれています。")
        return comment_list

    def write_files(self, *, is_latest: bool = False, should_get_task_histories_one_of_each: bool = False, should_download_annotation_zip: bool = True) -> None:
        """
        可視化に必要なファイルを作成します。
        原則、全件ファイルをダウンロードしてファイルを作成します。必要に応じて個別にAPIを実行してファイルを作成します。

        Args:
            is_latest: True なら最新のファイルをダウンロードする
            should_get_task_histories_one_of_each: Trueなら `get_task_histories` APIをタスク数だけ実行する。
                タスク全件ファイルは最新化できますが、タスク履歴全件ファイルは最新化できません。
                最新の状態を取得したいときに、このオプションを利用することを推奨しています。
        """

        downloading_obj = DownloadingFile(self.annofab_service)

        wait_options = WaitOptions(interval=60, max_tries=360)

        downloading_obj.download_task_json(self.project_id, dest_path=self.task_json_path, is_latest=is_latest, wait_options=wait_options)

        if should_download_annotation_zip:
            downloading_obj.download_annotation_zip(
                self.project_id,
                dest_path=self.annotation_zip_path,
                is_latest=is_latest,
                wait_options=wait_options,
            )

        try:
            downloading_obj.download_comment_json(self.project_id, dest_path=self.comment_json_path)
        except DownloadingFileNotFoundError:
            # プロジェクトを作成した日だと、コメント全件ファイルが作成されていないので、DownloadingFileNotFoundErrorが発生する
            # その場合でも、処理は継続できるので、空listのJSONファイルを作成して、処理が継続できるようにする。
            self.comment_json_path.write_text("[]", encoding="utf-8")

        try:
            downloading_obj.download_task_history_event_json(self.project_id, dest_path=self.task_history_event_json_path)
        except DownloadingFileNotFoundError:
            # プロジェクトを作成した日だと、タスク履歴全件ファイルが作成されていないので、DownloadingFileNotFoundErrorが発生する
            # その場合でも、処理は継続できるので、空listのJSONファイルを作成して、処理が継続できるようにする。
            self.task_history_event_json_path.write_text("[]", encoding="utf-8")

        if should_get_task_histories_one_of_each:
            # タスク履歴APIを一つずつ実行して、JSONファイルを生成する
            # 先にタスク全件ファイルをダウンロードする必要がある
            tasks = self.read_tasks_json()
            self._write_task_histories_json_with_executing_webapi([task["task_id"] for task in tasks])

        else:
            try:
                downloading_obj.download_task_history_json(self.project_id, dest_path=str(self.task_history_json_path))
            except DownloadingFileNotFoundError:
                # プロジェクトを作成した日だと、タスク履歴全件ファイルが作成されていないので、DownloadingFileNotFoundErrorが発生する
                # その場合でも、処理は継続できるので、タスク履歴APIを１個ずつ実行して、タスク履歴ファイルを作成する
                tasks = self.read_tasks_json()
                self._write_task_histories_json_with_executing_webapi([task["task_id"] for task in tasks])

    def _write_task_histories_json_with_executing_webapi(self, task_ids: Collection[str]) -> None:
        """
        `getTaskHistories` APIで取得したタスク履歴を取得して、ファイルに書き込みます。

        Args:
            task_ids: 取得対象のタスク一覧
        """
        logger.debug(f"{self.logging_prefix}: {len(task_ids)} 回 `get_task_histories` WebAPIを実行します。")

        task_index = 0
        result = {}
        for task_id in task_ids:
            if task_index % 100 == 0:
                logger.debug(f"{self.logging_prefix}: タスク履歴一覧取得中 {task_index} / {len(task_ids)} 件目")
            sub_task_histories, _ = self.annofab_service.api.get_task_histories(self.project_id, task_id)
            result[task_id] = sub_task_histories
            task_index += 1  # noqa: SIM113

        with self.task_history_json_path.open(mode="w", encoding="utf-8") as f:
            json.dump(result, f)

        logger.debug(f"{self.logging_prefix}: '{self.task_history_json_path}'に{len(result)}件のタスクの履歴情報を出力しました。")
