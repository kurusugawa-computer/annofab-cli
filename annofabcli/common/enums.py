from enum import Enum


class FormatArgument(Enum):
    """
    表示するフォーマット ``--format`` で指定できる値

    Attributes:
        CSV: CSV形式
        JSON: インデントされていないJSON形式
        PRETTY_JSON: インデントされているJSON形式

    """

    #: CSV形式
    CSV = "csv"

    #: 必要最小限の列に絞ったCSV形式
    MINIMAL_CSV = "minimal_csv"

    #: JSON形式
    JSON = "json"

    #: インデントされたJSON形式
    PRETTY_JSON = "pretty_json"

    #: input_data_idの一覧
    INPUT_DATA_ID_LIST = "input_data_id_list"

    #: task_idの一覧
    TASK_ID_LIST = "task_id_list"

    #: inspection_idの一覧
    INSPECTION_ID_LIST = "inspection_id_list"

    #: comment_idの一覧
    COMMENT_ID_LIST = "comment_id_list"

    #: user_idの一覧
    USER_ID_LIST = "user_id_list"

    #: project_idの一覧
    PROJECT_ID_LIST = "project_id_list"


class CustomProjectType(Enum):
    """カスタムプロジェクトの場合、検査コメントのフォーマットが分からないため、カスタムプロジェクトの種類をannofabcliで定義する。"""

    THREE_DIMENSION_POINT_CLOUD = "3dpc"
    """3DPCプロジェクト"""
