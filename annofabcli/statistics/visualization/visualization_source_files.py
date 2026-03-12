from __future__ import annotations

import json
import logging
from collections.abc import Collection
from pathlib import Path
from typing import Any

import annofabapi.utils

from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.download import DownloadingFile, get_filename
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

        # ダウンロードした一括情報（write_files()またはload_from_dir()で設定される）
        self.task_json_path: Path | None = None
        self.comment_json_path: Path | None = None
        self.task_history_json_path: Path | None = None
        self.task_history_event_json_path: Path | None = None
        self.annotation_zip_path: Path | None = None
        self.input_data_json_path: Path | None = None

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
        assert self.task_json_path is not None
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
        assert self.task_history_json_path is not None
        with self.task_history_json_path.open(encoding="utf-8") as f:
            task_histories_dict = json.load(f)

        logger.debug(f"{self.logging_prefix}: '{self.task_history_json_path}'を読み込みました。{len(task_histories_dict)}件のタスクの履歴が含まれています。")
        return task_histories_dict

    def read_task_history_events_json(self) -> list[dict[str, Any]]:
        """
        タスク履歴イベント全件ファイルを読み込みます。

        Returns:
            全タスクの履歴イベント情報
        """
        assert self.task_history_event_json_path is not None
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
        assert self.comment_json_path is not None
        with self.comment_json_path.open(encoding="utf-8") as f:
            comment_list = json.load(f)

        logger.debug(f"{self.logging_prefix}: '{self.comment_json_path}'を読み込みました。{len(comment_list)}件のコメントが含まれています。")
        return comment_list

    def read_input_data_json(self) -> list[dict[str, Any]]:
        """
        入力データ全件ファイルを読み込みます。

        Returns:
            全入力データの一覧
        """
        assert self.input_data_json_path is not None
        with self.input_data_json_path.open(encoding="utf-8") as f:
            input_data_list = json.load(f)

        logger.debug(f"{self.logging_prefix}: '{self.input_data_json_path}'を読み込みました。{len(input_data_list)}件の入力データが含まれています。")
        return input_data_list

    def get_video_duration_minutes_by_task_id(self) -> dict[str, float]:
        """
        動画プロジェクトの場合、タスクIDごとの動画の長さ（分単位）を取得します。

        Returns:
            key: task_id, value: 動画の長さ（分）
        """
        tasks = self.read_tasks_json()
        input_data_list = self.read_input_data_json()

        # 入力データIDをキーとした辞書を作成
        dict_input_data_by_id = {input_data["input_data_id"]: input_data for input_data in input_data_list}

        result = {}
        for task in tasks:
            task_id = task["task_id"]
            input_data_id_list = task["input_data_id_list"]
            assert len(input_data_id_list) == 1, f"task_id='{task_id}'には複数の入力データが含まれています。"
            input_data_id = input_data_id_list[0]
            input_data = dict_input_data_by_id.get(input_data_id)

            if input_data is None:
                logger.warning(f"task_id='{task_id}' :: タスクに含まれている入力データ（input_data_id='{input_data_id}'）は、見つかりません。")
                result[task_id] = 0.0
                continue

            video_duration_second = input_data["system_metadata"]["input_duration"]

            # 秒から分に変換
            result[task_id] = video_duration_second / 60.0

        return result

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

        self.task_json_path = downloading_obj.download_task_json_to_dir(self.project_id, self.target_dir, is_latest=is_latest, wait_options=wait_options)

        self.input_data_json_path = downloading_obj.download_input_data_json_to_dir(self.project_id, self.target_dir, is_latest=is_latest, wait_options=wait_options)

        if should_download_annotation_zip:
            self.annotation_zip_path = downloading_obj.download_annotation_zip_to_dir(
                self.project_id,
                self.target_dir,
                is_latest=is_latest,
                wait_options=wait_options,
            )

        try:
            self.comment_json_path = downloading_obj.download_comment_json_to_dir(self.project_id, self.target_dir)
        except DownloadingFileNotFoundError:
            # プロジェクトを作成した日だと、コメント全件ファイルが作成されていないので、DownloadingFileNotFoundErrorが発生する
            # その場合でも、処理は継続できるので、空listのJSONファイルを作成して、処理が継続できるようにする。
            self.comment_json_path = self.target_dir / get_filename(self.project_id, "comment", "json")
            self.comment_json_path.write_text("[]", encoding="utf-8")

        try:
            self.task_history_event_json_path = downloading_obj.download_task_history_event_json_to_dir(self.project_id, self.target_dir)
        except DownloadingFileNotFoundError:
            # プロジェクトを作成した日だと、タスク履歴全件ファイルが作成されていないので、DownloadingFileNotFoundErrorが発生する
            # その場合でも、処理は継続できるので、空listのJSONファイルを作成して、処理が継続できるようにする。
            self.task_history_event_json_path = self.target_dir / get_filename(self.project_id, "task_history_event", "json")
            self.task_history_event_json_path.write_text("[]", encoding="utf-8")

        if should_get_task_histories_one_of_each:
            # タスク履歴APIを一つずつ実行して、JSONファイルを生成する
            # 先にタスク全件ファイルをダウンロードする必要がある
            tasks = self.read_tasks_json()
            self._write_task_histories_json_with_executing_webapi([task["task_id"] for task in tasks])

        else:
            try:
                self.task_history_json_path = downloading_obj.download_task_history_json_to_dir(self.project_id, self.target_dir)
            except DownloadingFileNotFoundError:
                # プロジェクトを作成した日だと、タスク履歴全件ファイルが作成されていないので、DownloadingFileNotFoundErrorが発生する
                # その場合でも、処理は継続できるので、タスク履歴APIを１個ずつ実行して、タスク履歴ファイルを作成する
                tasks = self.read_tasks_json()
                self._write_task_histories_json_with_executing_webapi([task["task_id"] for task in tasks])

    def _find_latest_file(self, file_type: str, extension: str) -> Path | None:
        """target_dir内で命名規則``{timestamp}--{project_id}--{file_type}.{extension}``に一致する最新のファイルを探します。

        タイムスタンプ付きのファイル名をアルファベット順でソートした際の最後のファイル（最新のもの）を返します。

        Args:
            file_type: ファイルの種類（例: "task", "annotation"）
            extension: 拡張子（例: "json", "zip"）

        Returns:
            最新のファイルのパス。ファイルが見つからない場合はNone。
        """
        pattern = f"*--{self.project_id}--{file_type}.{extension}"
        files = sorted(self.target_dir.glob(pattern))
        return files[-1] if files else None

    def load_from_dir(self) -> None:
        """
        target_dir内の最新のダウンロード済みファイルからパスを設定します。

        ``--not_download``オプション使用時に呼び出します。
        ファイルが見つからない場合、対応するパス属性は``None``のままになります。
        そのため、ファイルが存在することを前提とする``read_*``メソッドを呼び出す前に、各パス属性がNoneでないことを確認してください。
        """
        self.task_json_path = self._find_latest_file("task", "json")
        self.input_data_json_path = self._find_latest_file("input_data", "json")
        self.annotation_zip_path = self._find_latest_file("annotation", "zip")
        self.comment_json_path = self._find_latest_file("comment", "json")
        self.task_history_json_path = self._find_latest_file("task_history", "json")
        self.task_history_event_json_path = self._find_latest_file("task_history_event", "json")

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

        if self.task_history_json_path is None:
            # write_files()でtask_history_json_pathが設定されていない場合（タスク履歴全件ファイルが存在しなかった場合など）に、
            # このメソッドが呼ばれることがある。その際のパスを設定する。
            self.task_history_json_path = self.target_dir / get_filename(self.project_id, "task_history", "json")

        with self.task_history_json_path.open(mode="w", encoding="utf-8") as f:
            json.dump(result, f)

        logger.debug(f"{self.logging_prefix}: '{self.task_history_json_path}'に{len(result)}件のタスクの履歴情報を出力しました。")
