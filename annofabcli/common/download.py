import asyncio
import datetime
import logging.config
from functools import partial
from pathlib import Path

import annofabapi
import requests
from annofabapi.models import JobStatus, ProjectJobType

from annofabcli.common.dataclasses import WaitOptions
from annofabcli.common.exceptions import DownloadingFileNotFoundError, UpdatedFileForDownloadingError

logger = logging.getLogger(__name__)

DOWNLOADING_FILETYPE_DICT = {
    ProjectJobType.GEN_TASKS_LIST: "タスク全件ファイル",
    ProjectJobType.GEN_INPUTS_LIST: "入力データ全件ファイル",
    ProjectJobType.GEN_ANNOTATION: "アノテーションzip",
}

DEFAULT_WAIT_OPTIONS = WaitOptions(interval=60, max_tries=360)


def get_filename(project_id: str, file_type: str, extension: str) -> str:
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")  # noqa: DTZ005
    return f"{timestamp}--{project_id}--{file_type}.{extension}"


class DownloadingFile:
    def __init__(self, service: annofabapi.Resource) -> None:
        self.service = service

    @staticmethod
    def get_max_wait_minutes(wait_options: WaitOptions) -> float:
        return wait_options.max_tries * wait_options.interval / 60

    def request_update(self, project_id: str, job_type: ProjectJobType) -> str:
        """ダウンロード用ファイルの更新を要求する。

        Args:
            project_id: 対象のプロジェクトID。
            job_type: 更新対象のジョブ種別。

        Returns:
            開始した更新ジョブ、または競合した既存ジョブのID。

        Raises:
            UpdatedFileForDownloadingError: 競合した既存ジョブが見つからない場合。
        """
        update_functions = {
            ProjectJobType.GEN_TASKS_LIST: self.service.api.post_project_tasks_update,
            ProjectJobType.GEN_INPUTS_LIST: self.service.api.post_project_inputs_update,
            ProjectJobType.GEN_ANNOTATION: self.service.api.post_annotation_archive_update,
        }
        try:
            job = update_functions[job_type](project_id)[0]["job"]
            return job["job_id"]
        except requests.HTTPError as e:
            if e.response.status_code != requests.codes.conflict:
                raise
            logger.warning(f"project_id='{project_id}', job_type='{job_type.value}' :: 更新要求が競合したため、既存の更新ジョブを参照します。", exc_info=True)

        jobs = self.service.api.get_project_job(project_id, query_params={"type": job_type.value})[0]["list"]
        if not jobs:
            raise UpdatedFileForDownloadingError(f"{DOWNLOADING_FILETYPE_DICT[job_type]}の更新ジョブが見つかりませんでした。")
        return jobs[0]["job_id"]

    def wait_for_completion(
        self,
        project_id: str,
        job_type: ProjectJobType,
        job_id: str,
        wait_options: WaitOptions | None = None,
    ) -> None:
        """指定した更新ジョブが成功するまで待つ。

        Args:
            project_id: 対象のプロジェクトID。
            job_type: 更新対象のジョブ種別。
            job_id: 待機するジョブのID。
            wait_options: 完了確認の間隔と回数。

        Returns:
            None

        Raises:
            UpdatedFileForDownloadingError: ジョブが失敗、タイムアウト、または存在しない場合。
        """
        if wait_options is None:
            wait_options = DEFAULT_WAIT_OPTIONS

        max_wait_minutes = self.get_max_wait_minutes(wait_options)
        filetype = DOWNLOADING_FILETYPE_DICT[job_type]
        logger.info(f"{filetype}の更新処理が完了するまで、最大{max_wait_minutes}分間待ちます。job_id='{job_id}'")
        result = self.service.wrapper.wait_until_job_finished(
            project_id,
            job_type=job_type,
            job_id=job_id,
            job_access_interval=wait_options.interval,
            max_job_access=wait_options.max_tries,
        )
        if result != JobStatus.SUCCEEDED:
            raise UpdatedFileForDownloadingError(f"{filetype}の更新処理が{max_wait_minutes}分以内に完了しない、または更新処理に失敗しました。")

    async def download_annotation_zip_with_async(
        self,
        project_id: str,
        dest_path: str | Path,
        is_latest: bool = False,  # noqa: FBT001, FBT002
        wait_options: WaitOptions | None = None,
    ) -> None:
        loop = asyncio.get_event_loop()
        partial_func = partial(self.download_annotation_zip, project_id, dest_path, is_latest, wait_options)
        await loop.run_in_executor(None, partial_func)

    def download_annotation_zip(
        self,
        project_id: str,
        dest_path: str | Path,
        is_latest: bool = False,  # noqa: FBT001, FBT002
        wait_options: WaitOptions | None = None,
        should_download_full_annotation: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        """アノテーションZIPをダウンロードします。"""

        def download_annotation_zip() -> None:
            if should_download_full_annotation:
                self.service.wrapper.download_full_annotation_archive(project_id, dest_path)
            else:
                self.service.wrapper.download_annotation_zip(project_id, dest_path)

        if is_latest:
            self.wait_until_updated_annotation_zip(project_id, wait_options)
            download_annotation_zip()

        else:
            try:
                download_annotation_zip()
            except requests.HTTPError as e:
                if e.response.status_code == requests.codes.not_found:
                    logger.info("アノテーションzipが存在しなかったので、アノテーションzipファイルの更新処理を実行します。")
                    self.wait_until_updated_annotation_zip(project_id, wait_options)
                    download_annotation_zip()
                else:
                    raise e  # noqa: TRY201

    def wait_until_updated_annotation_zip(self, project_id: str, wait_options: WaitOptions | None = None) -> None:
        job_id = self.request_update(project_id, ProjectJobType.GEN_ANNOTATION)
        self.wait_for_completion(project_id, job_type=ProjectJobType.GEN_ANNOTATION, job_id=job_id, wait_options=wait_options)

    async def download_input_data_json_with_async(
        self,
        project_id: str,
        dest_path: str | Path,
        is_latest: bool = False,  # noqa: FBT001, FBT002
        wait_options: WaitOptions | None = None,
    ) -> None:
        loop = asyncio.get_event_loop()
        partial_func = partial(self.download_input_data_json, project_id, dest_path, is_latest, wait_options)
        await loop.run_in_executor(None, partial_func)

    def download_input_data_json(
        self,
        project_id: str,
        dest_path: str | Path,
        is_latest: bool = False,  # noqa: FBT001, FBT002
        wait_options: WaitOptions | None = None,
    ) -> None:
        if is_latest:
            self.wait_until_updated_input_data_json(project_id, wait_options)
            self.service.wrapper.download_project_inputs_json(project_id, dest_path)

        else:
            try:
                self.service.wrapper.download_project_inputs_json(project_id, dest_path)
            except requests.HTTPError as e:
                if e.response.status_code == requests.codes.not_found:
                    logger.info("入力データ全件ファイルが存在しなかったので、入力データ全件ファイルの更新処理を実行します。")
                    self.wait_until_updated_input_data_json(project_id, wait_options)
                    self.service.wrapper.download_project_inputs_json(project_id, dest_path)
                else:
                    raise e  # noqa: TRY201

    def wait_until_updated_input_data_json(self, project_id: str, wait_options: WaitOptions | None = None) -> None:
        job_id = self.request_update(project_id, ProjectJobType.GEN_INPUTS_LIST)
        self.wait_for_completion(project_id, job_type=ProjectJobType.GEN_INPUTS_LIST, job_id=job_id, wait_options=wait_options)

    async def download_task_json_with_async(
        self,
        project_id: str,
        dest_path: str | Path,
        is_latest: bool = False,  # noqa: FBT001, FBT002
        wait_options: WaitOptions | None = None,
    ) -> None:
        loop = asyncio.get_event_loop()
        partial_func = partial(self.download_task_json, project_id, dest_path, is_latest=is_latest, wait_options=wait_options)
        await loop.run_in_executor(None, partial_func)

    def download_task_json(self, project_id: str, dest_path: str | Path, *, is_latest: bool = False, wait_options: WaitOptions | None = None) -> None:
        if is_latest:
            self.wait_until_updated_task_json(project_id, wait_options)
            self.service.wrapper.download_project_tasks_json(project_id, dest_path)

        else:
            try:
                self.service.wrapper.download_project_tasks_json(project_id, dest_path)
            except requests.HTTPError as e:
                if e.response.status_code == requests.codes.not_found:
                    logger.info("タスク全件ファイルが存在しなかったので、タスク全件ファイルの更新処理を実行します。")
                    self.wait_until_updated_task_json(project_id, wait_options)
                    self.service.wrapper.download_project_tasks_json(project_id, dest_path)
                else:
                    raise e  # noqa: TRY201

    def wait_until_updated_task_json(self, project_id: str, wait_options: WaitOptions | None = None) -> None:
        job_id = self.request_update(project_id, ProjectJobType.GEN_TASKS_LIST)
        self.wait_for_completion(project_id, job_type=ProjectJobType.GEN_TASKS_LIST, job_id=job_id, wait_options=wait_options)

    async def download_task_history_json_with_async(self, project_id: str, dest_path: str | Path) -> None:
        """
        非同期でタスク履歴全件ファイルをダウンロードする。

        Raises:
            DownloadingFileNotFoundError:
        """
        return self.download_task_history_json(project_id, dest_path=dest_path)

    def download_task_history_json(self, project_id: str, dest_path: str | Path) -> None:
        """
        タスク履歴全件ファイルをダウンロードする。

        Args:
            project_id:
            dest_path:

        Raises:
            DownloadingFileNotFoundError:
        """
        try:
            self.service.wrapper.download_project_task_histories_json(project_id, dest_path)
        except requests.HTTPError as e:
            if e.response.status_code == requests.codes.not_found:
                raise DownloadingFileNotFoundError(f"project_id='{project_id}'のプロジェクトに、タスク履歴全件ファイルが存在しないため、ダウンロードできませんでした。") from e
            raise e  # noqa: TRY201

    def download_task_history_event_json(self, project_id: str, dest_path: str | Path) -> None:
        """
        タスク履歴イベント全件ファイルをダウンロードする。

        Args:
            project_id:
            dest_path:

        Raises:
            DownloadingFileNotFoundError:
        """
        try:
            self.service.wrapper.download_project_task_history_events_json(project_id, dest_path)
        except requests.HTTPError as e:
            if e.response.status_code == requests.codes.not_found:
                raise DownloadingFileNotFoundError(f"project_id='{project_id}'のプロジェクトに、タスク履歴イベント全件ファイルが存在しないため、ダウンロードできませんでした。") from e
            raise e  # noqa: TRY201

    async def download_task_history_event_json_with_async(self, project_id: str, dest_path: str | Path) -> None:
        """
        非同期でタスク履歴全件ファイルをダウンロードする。


        Raises:
            DownloadingFileNotFoundError:
        """
        return self.download_task_history_event_json(project_id, dest_path=dest_path)

    async def download_comment_json_with_async(self, project_id: str, dest_path: str | Path) -> None:
        """
        非同期でコメント全件ファイルをダウンロードする。

        Raises:
            DownloadingFileNotFoundError:
        """

        return self.download_comment_json(project_id, dest_path=dest_path)

    def download_comment_json(self, project_id: str, dest_path: str | Path) -> None:
        """
        コメント全件ファイルをダウンロードする。


        Raises:
            DownloadingFileNotFoundError:
        """
        try:
            self.service.wrapper.download_project_comments_json(project_id, dest_path)
        except requests.HTTPError as e:
            if e.response.status_code == requests.codes.not_found:
                raise DownloadingFileNotFoundError(f"project_id='{project_id}'のプロジェクトに、コメント全件ファイルが存在しないため、ダウンロードできませんでした。") from e
            raise e  # noqa: TRY201

    # 統一された命名規則でファイルをダウンロードする関数群
    def download_annotation_zip_to_dir(
        self,
        project_id: str,
        output_dir: Path,
        *,
        is_latest: bool = False,
        wait_options: WaitOptions | None = None,
    ) -> Path:
        """
        アノテーションZIPをoutput_dirに統一された命名規則でダウンロードする。

        Args:
            project_id: プロジェクトID
            output_dir: 出力ディレクトリ
            is_latest: 最新版をダウンロードするかどうか
            wait_options: 待機オプション

        Returns:
            ダウンロードされたファイルのパス
        """
        dest_path = output_dir / get_filename(project_id, "annotation", "zip")

        self.download_annotation_zip(
            project_id,
            dest_path=str(dest_path),
            is_latest=is_latest,
            wait_options=wait_options,
        )
        return dest_path

    def download_task_json_to_dir(
        self,
        project_id: str,
        output_dir: Path,
        *,
        is_latest: bool = False,
        wait_options: WaitOptions | None = None,
    ) -> Path:
        """
        タスクJSONをoutput_dirに統一された命名規則でダウンロードする。

        Args:
            project_id: プロジェクトID
            output_dir: 出力ディレクトリ
            is_latest: 最新版をダウンロードするかどうか
            wait_options: 待機オプション

        Returns:
            ダウンロードされたファイルのパス
        """
        dest_path = output_dir / get_filename(project_id, "task", "json")

        self.download_task_json(
            project_id,
            dest_path=str(dest_path),
            is_latest=is_latest,
            wait_options=wait_options,
        )
        return dest_path

    def download_input_data_json_to_dir(
        self,
        project_id: str,
        output_dir: Path,
        *,
        is_latest: bool = False,
        wait_options: WaitOptions | None = None,
    ) -> Path:
        """
        入力データJSONをoutput_dirに統一された命名規則でダウンロードする。

        Args:
            project_id: プロジェクトID
            output_dir: 出力ディレクトリ
            is_latest: 最新版をダウンロードするかどうか
            wait_options: 待機オプション

        Returns:
            ダウンロードされたファイルのパス
        """
        dest_path = output_dir / get_filename(project_id, "input_data", "json")

        self.download_input_data_json(
            project_id,
            dest_path=str(dest_path),
            is_latest=is_latest,
            wait_options=wait_options,
        )
        return dest_path

    def download_task_history_json_to_dir(
        self,
        project_id: str,
        output_dir: Path,
    ) -> Path:
        """
        タスク履歴JSONをoutput_dirに統一された命名規則でダウンロードする。

        Args:
            project_id: プロジェクトID
            output_dir: 出力ディレクトリ

        Returns:
            ダウンロードされたファイルのパス
        """
        dest_path = output_dir / get_filename(project_id, "task_history", "json")

        self.download_task_history_json(
            project_id,
            dest_path=str(dest_path),
        )
        return dest_path

    def download_task_history_event_json_to_dir(
        self,
        project_id: str,
        output_dir: Path,
    ) -> Path:
        """
        タスク履歴イベントJSONをoutput_dirに統一された命名規則でダウンロードする。

        Args:
            project_id: プロジェクトID
            output_dir: 出力ディレクトリ

        Returns:
            ダウンロードされたファイルのパス
        """
        dest_path = output_dir / get_filename(project_id, "task_history_event", "json")

        self.download_task_history_event_json(
            project_id,
            dest_path=str(dest_path),
        )
        return dest_path

    def download_comment_json_to_dir(
        self,
        project_id: str,
        output_dir: Path,
    ) -> Path:
        """
        コメントJSONをoutput_dirに統一された命名規則でダウンロードする。

        Args:
            project_id: プロジェクトID
            output_dir: 出力ディレクトリ

        Returns:
            ダウンロードされたファイルのパス
        """
        dest_path = output_dir / get_filename(project_id, "comment", "json")

        self.download_comment_json(
            project_id,
            dest_path=str(dest_path),
        )
        return dest_path
