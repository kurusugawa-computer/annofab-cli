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
    CSV = 'csv'

    #: JSON形式
    JSON = 'json'

    #: インデントされたJSON形式
    PRETTY_JSON = 'pretty_json'

    #: task_idの一覧
    TASK_ID_LIST = 'task_id_list'

    #: inspection_idの一覧
    INSPECTION_ID_LIST = 'inspection_id_list'

    #: user_idの一覧
    USER_ID_LIST = 'user_id_list'
