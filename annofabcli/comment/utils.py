from annofabapi.models import CommentType


def get_comment_type_name(comment_type) -> str:
    if comment_type == CommentType.INSPECTION:
        return "検査コメント"
    elif comment_type == CommentType.ONHOLD:
        return "保留コメント"
    else:
        raise RuntimeError(f"{comment_type=}は無効な値です。")
