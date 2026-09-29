from __future__ import annotations

import argparse
import datetime
import json
import logging
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import annofabapi

import annofabcli.common.cli
from annofabcli.common.cli import COMMAND_LINE_ERROR_STATUS_CODE

logger = logging.getLogger(__name__)

JST = datetime.timezone(datetime.timedelta(hours=9))
"""日本標準時。"""

_DATETIME_PATTERN = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})"
    r"(?:T(?P<hour>\d{2}):(?P<minute>\d{2})"
    r"(?::(?P<second>\d{2})(?P<fraction>\.\d{1,6})?)?"
    r"(?P<timezone>Z|[+-]\d{2}:\d{2})?)?$"
)
"""履歴の更新日時として受け付ける形式。"""


@dataclass(frozen=True)
class DatetimeRange:
    """更新日時を検索する半開区間。"""

    start: datetime.datetime
    """検索区間の開始日時。"""

    end: datetime.datetime
    """検索区間の終了日時。"""


def parse_updated_datetime(value: str) -> DatetimeRange:
    """入力された精度に対応する日時範囲へ変換する。

    Args:
        value: ISO 8601形式の日付または日時。タイムゾーン省略時はJSTとして扱う。

    Returns:
        入力された日、分、秒、または小数秒に対応する半開区間。

    Raises:
        ValueError: 日時の形式または値が不正な場合。
    """

    match = _DATETIME_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError("ISO 8601形式（YYYY-MM-DDまたはYYYY-MM-DDTHH:MM[:SS[.ffffff]][Z|±HH:MM]）で指定してください。")

    normalized_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        if match.group("hour") is None:
            start = datetime.datetime.combine(datetime.date.fromisoformat(value), datetime.time(), tzinfo=JST)
            resolution = datetime.timedelta(days=1)
        else:
            start = datetime.datetime.fromisoformat(normalized_value)
            if start.tzinfo is None:
                start = start.replace(tzinfo=JST)

            fraction = match.group("fraction")
            if fraction is not None:
                resolution = datetime.timedelta(microseconds=10 ** (6 - len(fraction[1:])))
            elif match.group("second") is not None:
                resolution = datetime.timedelta(seconds=1)
            else:
                resolution = datetime.timedelta(minutes=1)
    except ValueError as exc:
        raise ValueError(f"日時の値が不正です。 :: value='{value}'") from exc

    return DatetimeRange(start=start, end=start + resolution)


def validate_updated_datetime_argument(value: str) -> str:
    """更新日時のコマンドライン引数を検証する。

    Args:
        value: ISO 8601形式の日付または日時。

    Returns:
        検証済みの入力値。

    Raises:
        argparse.ArgumentTypeError: 日時が不正な場合。
    """

    try:
        parse_updated_datetime(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return value


def find_histories_by_updated_datetime(histories: Sequence[Mapping[str, Any]], value: str) -> list[Mapping[str, Any]]:
    """指定された更新日時の範囲に含まれる履歴を検索する。

    Args:
        histories: アノテーション仕様の履歴一覧。
        value: ISO 8601形式の日付または日時。

    Returns:
        更新日時の新しい順に並んだ該当履歴。
    """

    datetime_range = parse_updated_datetime(value)
    matched_histories = []
    for history in histories:
        history_datetime = datetime.datetime.fromisoformat(history["updated_datetime"])
        if datetime_range.start <= history_datetime < datetime_range.end:
            matched_histories.append(history)

    return sorted(matched_histories, key=lambda history: datetime.datetime.fromisoformat(history["updated_datetime"]), reverse=True)


def get_history_id_from_before_index(service: annofabapi.Resource, project_id: str, before: int) -> str | None:
    """最新からの相対位置で履歴IDを取得する。

    Args:
        service: Annofab APIリソース。
        project_id: 対象プロジェクトのproject_id。
        before: 最新から遡る履歴数。

    Returns:
        該当する履歴ID。履歴が存在しない場合はNone。
    """

    histories, _ = service.api.get_annotation_specs_histories(project_id)
    sorted_histories = sorted(histories, key=lambda history: datetime.datetime.fromisoformat(history["updated_datetime"]), reverse=True)
    if before >= len(sorted_histories):
        logger.warning(f"アノテーション仕様の履歴は{len(sorted_histories)}個のため、最新より{before}個前のアノテーション仕様は見つかりませんでした。")
        return None

    history = sorted_histories[before]
    logger.info(f"{history['updated_datetime']}のアノテーション仕様を参照します。 :: history_id='{history['history_id']}', comment='{history.get('comment')}'")
    return history["history_id"]


def resolve_history_id_or_exit(
    service: annofabapi.Resource,
    project_id: str,
    *,
    history_id: str | None,
    before: int | None,
    updated_datetime: str | None,
    common_message: str,
    option_prefix: str = "",
) -> str | None:
    """CLI引数から参照対象の履歴IDを解決する。

    Args:
        service: Annofab APIリソース。
        project_id: 対象プロジェクトのproject_id。
        history_id: 明示的に指定された履歴ID。
        before: 最新から遡る履歴数。
        updated_datetime: 検索する履歴の更新日時。
        common_message: コマンドラインエラーの接頭辞。
        option_prefix: ``left_`` などのオプション名の接頭辞。

    Returns:
        参照対象の履歴ID。最新版を参照する場合はNone。
    """

    if history_id is not None:
        return history_id

    if before is not None:
        resolved_history_id = get_history_id_from_before_index(service, project_id, before)
        if resolved_history_id is None:
            print(  # noqa: T201
                f"{common_message} argument --{option_prefix}before: 最新より{before}個前のアノテーション仕様は見つかりませんでした。",
                file=sys.stderr,
            )
            raise SystemExit(COMMAND_LINE_ERROR_STATUS_CODE)
        return resolved_history_id

    if updated_datetime is None:
        return None

    histories, _ = service.api.get_annotation_specs_histories(project_id)
    try:
        matched_histories = find_histories_by_updated_datetime(histories, updated_datetime)
    except ValueError as exc:
        print(f"{common_message} argument --{option_prefix}updated_datetime: {exc}", file=sys.stderr)  # noqa: T201
        raise SystemExit(COMMAND_LINE_ERROR_STATUS_CODE) from exc

    if len(matched_histories) == 0:
        print(  # noqa: T201
            f"{common_message} argument --{option_prefix}updated_datetime: '{updated_datetime}'に一致するアノテーション仕様は見つかりませんでした。"
            " `annotation_specs list_history`で履歴を確認してください。",
            file=sys.stderr,
        )
        raise SystemExit(COMMAND_LINE_ERROR_STATUS_CODE)

    if len(matched_histories) > 1:
        print(  # noqa: T201
            f"{common_message} argument --{option_prefix}updated_datetime: '{updated_datetime}'に一致するアノテーション仕様が複数見つかりました。"
            " 日時を詳細にするか、以下のhistory_idを指定してください。",
            file=sys.stderr,
        )
        for history in matched_histories:
            print(  # noqa: T201
                f"  updated_datetime='{history['updated_datetime']}', history_id='{history['history_id']}', comment='{history.get('comment')}'",
                file=sys.stderr,
            )
        raise SystemExit(COMMAND_LINE_ERROR_STATUS_CODE)

    history = matched_histories[0]
    logger.info(f"{history['updated_datetime']}のアノテーション仕様を参照します。 :: history_id='{history['history_id']}', comment='{history.get('comment')}'")
    return history["history_id"]


def load_annotation_specs_or_exit(
    service: annofabapi.Resource,
    *,
    project_id: str | None,
    annotation_specs_json_file: Path | None,
    history_id: str | None,
    before: int | None,
    updated_datetime: str | None,
    common_message: str,
) -> dict[str, Any]:
    """プロジェクトまたはJSONファイルからアノテーション仕様を読み込む。

    Args:
        service: Annofab APIリソース。
        project_id: 対象プロジェクトのproject_id。
        annotation_specs_json_file: アノテーション仕様JSONのパス。
        history_id: 明示的に指定された履歴ID。
        before: 最新から遡る履歴数。
        updated_datetime: 検索する履歴の更新日時。
        common_message: コマンドラインエラーの接頭辞。

    Returns:
        アノテーション仕様。
    """

    if project_id is not None:
        resolved_history_id = resolve_history_id_or_exit(
            service,
            project_id,
            history_id=history_id,
            before=before,
            updated_datetime=updated_datetime,
            common_message=common_message,
        )
        query_params = {"v": "3"}
        if resolved_history_id is not None:
            query_params["history_id"] = resolved_history_id
        annotation_specs, _ = service.api.get_annotation_specs(project_id, query_params=query_params)
        return annotation_specs

    if annotation_specs_json_file is None:
        raise RuntimeError("'--project_id'か'--annotation_specs_json_file'のどちらかを指定する必要があります。")

    if history_id is not None or before is not None or updated_datetime is not None:
        print(  # noqa: T201
            f"{common_message} argument --history_id/--before/--updated_datetime: '--annotation_specs_json_file' を指定したときは指定できません。",
            file=sys.stderr,
        )
        raise SystemExit(COMMAND_LINE_ERROR_STATUS_CODE)

    with annotation_specs_json_file.open(encoding="utf-8") as file_pointer:
        return json.load(file_pointer)


def add_history_arguments(parser: argparse.ArgumentParser | argparse._ArgumentGroup, *, prefix: str = "") -> None:
    """アノテーション仕様の履歴を選択する引数を追加する。

    Args:
        parser: 引数を追加するパーサー。
        prefix: ``left_`` などのオプション名の接頭辞。

    Returns:
        なし。
    """

    history_group = parser.add_mutually_exclusive_group()
    history_group.add_argument(
        f"--{prefix}history_id",
        type=str,
        help="参照するアノテーション仕様のhistory_id。指定しない場合は最新のアノテーション仕様を参照します。",
    )
    history_group.add_argument(
        f"--{prefix}before",
        type=annofabcli.common.cli.non_negative_int,
        help="参照するアノテーション仕様が最新よりいくつ前かを指定します。たとえば ``1`` は最新より1個前を表します。",
    )
    history_group.add_argument(
        f"--{prefix}updated_datetime",
        type=validate_updated_datetime_argument,
        help=("参照するアノテーション仕様の更新日時をISO 8601形式で指定します。日、分、秒、小数秒の精度で検索し、1件に特定できる必要があります。 タイムゾーンを省略した場合はJSTとして扱います。"),
    )
