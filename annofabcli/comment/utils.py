import logging
from collections import defaultdict
from collections.abc import Collection
from typing import Any

from annofabapi.models import CommentType

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


def _get_comment_datetime_for_sorting(comment: dict[str, Any]) -> str:
    return comment["datetime_for_sorting"]


def _create_reply_comment_for_output(reply_comment: dict[str, Any]) -> dict[str, Any]:
    output_reply_comment = dict(reply_comment)
    output_reply_comment.pop("reply_count", None)
    return output_reply_comment


def create_comment_list_with_replies(comment_list: Collection[dict[str, Any]]) -> list[dict[str, Any]]:
    """ルートコメントに返信コメント一覧を付与したコメント一覧を生成します。

    Args:
        comment_list: コメント一覧

    Returns:
        ``reply_comments`` を付与したルートコメント一覧
    """

    root_comments: list[dict[str, Any]] = []
    reply_comments_by_root_key: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    root_comment_key_set: set[tuple[str, str, str]] = set()

    for comment in comment_list:
        comment_node = comment["comment_node"]
        node_type = comment_node["_type"]

        if node_type == "Root":
            root_key = (comment["task_id"], comment["input_data_id"], comment["comment_id"])
            root_comments.append(comment)
            root_comment_key_set.add(root_key)
        elif node_type == "Reply":
            root_key = (comment["task_id"], comment["input_data_id"], comment_node["root_comment_id"])
            reply_comments_by_root_key[root_key].append(comment)
        else:
            logger.warning(f"未知のコメントノード種別のため、スキップします。comment_node._type='{node_type}', comment_id='{comment['comment_id']}'")

    for root_key in reply_comments_by_root_key:
        if root_key not in root_comment_key_set:
            logger.warning(f"返信先のルートコメントが存在しないため、返信コメントをスキップします。task_id='{root_key[0]}', input_data_id='{root_key[1]}', root_comment_id='{root_key[2]}'")

    sorted_root_comments = sorted(root_comments, key=_get_comment_datetime_for_sorting)
    comment_list_with_replies: list[dict[str, Any]] = []
    for root_comment in sorted_root_comments:
        root_key = (root_comment["task_id"], root_comment["input_data_id"], root_comment["comment_id"])
        reply_comments = sorted(reply_comments_by_root_key.get(root_key, []), key=_get_comment_datetime_for_sorting)
        root_comment_with_replies = dict(root_comment)
        root_comment_with_replies["reply_comments"] = [_create_reply_comment_for_output(e) for e in reply_comments]
        comment_list_with_replies.append(root_comment_with_replies)

    return comment_list_with_replies


logger = logging.getLogger(__name__)


def get_comment_type_name(comment_type: CommentType) -> str:
    if comment_type == CommentType.INSPECTION:
        return "検査コメント"
    elif comment_type == CommentType.ONHOLD:
        return "保留コメント"
    else:
        raise RuntimeError(f"{comment_type=}は無効な値です。")


def _get_comment_datetime_for_sorting(comment: dict[str, Any]) -> str:
    return comment["datetime_for_sorting"]


def create_comment_list_with_replies(comment_list: Collection[dict[str, Any]]) -> list[dict[str, Any]]:
    """ルートコメントに返信コメント一覧を付与したコメント一覧を生成します。

    Args:
        comment_list: コメント一覧

    Returns:
        ``reply_comments`` を付与したルートコメント一覧
    """

    root_comments: list[dict[str, Any]] = []
    reply_comments_by_root_key: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    root_comment_key_set: set[tuple[str, str, str]] = set()

    for comment in comment_list:
        comment_node = comment["comment_node"]
        node_type = comment_node["_type"]

        if node_type == "Root":
            root_key = (comment["task_id"], comment["input_data_id"], comment["comment_id"])
            root_comments.append(comment)
            root_comment_key_set.add(root_key)
        elif node_type == "Reply":
            root_key = (comment["task_id"], comment["input_data_id"], comment_node["root_comment_id"])
            reply_comments_by_root_key[root_key].append(comment)
        else:
            logger.warning(f"未知のコメントノード種別のため、スキップします。comment_node._type='{node_type}', comment_id='{comment['comment_id']}'")

    for root_key in reply_comments_by_root_key:
        if root_key not in root_comment_key_set:
            logger.warning(f"返信先のルートコメントが存在しないため、返信コメントをスキップします。task_id='{root_key[0]}', input_data_id='{root_key[1]}', root_comment_id='{root_key[2]}'")

    sorted_root_comments = sorted(root_comments, key=_get_comment_datetime_for_sorting)
    comment_list_with_replies: list[dict[str, Any]] = []
    for root_comment in sorted_root_comments:
        root_key = (root_comment["task_id"], root_comment["input_data_id"], root_comment["comment_id"])
        reply_comments = sorted(reply_comments_by_root_key.get(root_key, []), key=_get_comment_datetime_for_sorting)
        root_comment_with_replies = dict(root_comment)
        root_comment_with_replies["reply_comments"] = [_copy_reply_comment(e) for e in reply_comments]
        comment_list_with_replies.append(root_comment_with_replies)

    return comment_list_with_replies


def _copy_reply_comment(comment: dict[str, Any]) -> dict[str, Any]:
    reply_comment = dict(comment)
    reply_comment.pop("reply_count", None)
    return reply_comment


def _get_comment_datetime_for_sorting(comment: dict[str, Any]) -> str:
    return comment["datetime_for_sorting"]


def _create_reply_comment_for_output(comment: dict[str, Any]) -> dict[str, Any]:
    reply_comment = dict(comment)
    reply_comment.pop("reply_count", None)
    return reply_comment


def create_comment_list_with_replies(comment_list: Collection[dict[str, Any]]) -> list[dict[str, Any]]:
    """ルートコメントに返信コメント一覧を付与したコメント一覧を生成します。

    Args:
        comment_list: コメント一覧

    Returns:
        ``reply_comments`` を付与したルートコメント一覧
    """

    root_comments: list[dict[str, Any]] = []
    reply_comments_by_root_key: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    root_comment_key_set: set[tuple[str, str, str]] = set()

    for comment in comment_list:
        comment_node = comment["comment_node"]
        node_type = comment_node["_type"]

        if node_type == "Root":
            root_key = (comment["task_id"], comment["input_data_id"], comment["comment_id"])
            root_comments.append(comment)
            root_comment_key_set.add(root_key)
        elif node_type == "Reply":
            root_key = (comment["task_id"], comment["input_data_id"], comment_node["root_comment_id"])
            reply_comments_by_root_key[root_key].append(comment)
        else:
            logger.warning(f"未知のコメントノード種別のため、スキップします。comment_node._type='{node_type}', comment_id='{comment['comment_id']}'")

    for root_key in reply_comments_by_root_key:
        if root_key not in root_comment_key_set:
            logger.warning(f"返信先のルートコメントが存在しないため、返信コメントをスキップします。task_id='{root_key[0]}', input_data_id='{root_key[1]}', root_comment_id='{root_key[2]}'")

    sorted_root_comments = sorted(root_comments, key=_get_comment_datetime_for_sorting)
    comment_list_with_replies: list[dict[str, Any]] = []
    for root_comment in sorted_root_comments:
        root_key = (root_comment["task_id"], root_comment["input_data_id"], root_comment["comment_id"])
        reply_comments = sorted(reply_comments_by_root_key.get(root_key, []), key=_get_comment_datetime_for_sorting)
        root_comment_with_replies = dict(root_comment)
        root_comment_with_replies["reply_comments"] = [_create_reply_comment_for_output(e) for e in reply_comments]
        comment_list_with_replies.append(root_comment_with_replies)

    return comment_list_with_replies
