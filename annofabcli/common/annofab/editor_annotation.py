import logging
from collections.abc import Collection
from typing import Any

import annofabapi

logger = logging.getLogger(__name__)

BULK_REQUEST_SIZE = 10
"""getEditorAnnotationsInBulk APIに渡す入力データIDの最大件数。"""


def get_editor_annotation_dict_in_bulk(
    service: annofabapi.Resource,
    project_id: str,
    task_id: str,
    input_data_id_list: Collection[str],
) -> dict[str, dict[str, Any]]:
    """同一タスクのアノテーションをバルク取得し、IDをキーとする辞書で返す。

    バルク取得に失敗した入力データは個別取得へフォールバックする。個別取得にも
    失敗した入力データは戻り値に含めない。

    Args:
        service: Annofab APIのリソース。
        project_id: プロジェクトID。
        task_id: タスクID。
        input_data_id_list: 取得対象の入力データID。

    Returns:
        入力データIDをキー、アノテーション情報を値とする辞書。
    """
    input_data_id_list = list(dict.fromkeys(input_data_id_list))
    annotation_dict: dict[str, dict[str, Any]] = {}

    for initial_index in range(0, len(input_data_id_list), BULK_REQUEST_SIZE):
        batch_input_data_id_list = input_data_id_list[initial_index : initial_index + BULK_REQUEST_SIZE]
        try:
            response, _ = service.api.get_editor_annotations_in_bulk(
                project_id,
                task_id,
                query_params={"input_data_id": ",".join(batch_input_data_id_list)},
            )
            successful_annotation_list = response["success"]
            failed_input_data_id_list = [failure_info["input_data_id"] for failure_info in response["failure"]]
        except Exception:
            logger.warning(f"task_id='{task_id}' :: バルク取得APIで失敗したため、個別に再取得します。", exc_info=True)
            successful_annotation_list = []
            failed_input_data_id_list = batch_input_data_id_list

        for annotation in successful_annotation_list:
            annotation_dict[annotation["input_data_id"]] = annotation

        for input_data_id in failed_input_data_id_list:
            logger.warning(f"task_id='{task_id}', input_data_id='{input_data_id}' :: バルク取得APIで失敗したため、個別に再取得します。")
            try:
                annotation, _ = service.api.get_editor_annotation(project_id, task_id, input_data_id, query_params={"v": "2"})
            except Exception:
                logger.warning(f"task_id='{task_id}', input_data_id='{input_data_id}' :: 個別取得APIでもアノテーション情報の取得に失敗しました。", exc_info=True)
                continue
            annotation_dict[input_data_id] = annotation

    return annotation_dict
