==========================================
comment list
==========================================

Description
=================================
コメント一覧を出力します。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドを実行すると、コメント（検査コメントまたは保留コメント）の一覧が出力されます。

.. code-block::

    $ annofabcli comment list --project_id prj1 --task_id task1 task2


``--comment_type`` を指定すると、コメントの種類で絞り込めます。

.. code-block::

    # 検査コメントを出力
    $ annofabcli comment list --project_id prj1 --task_id task1 task2 \
     --comment_type inspection

    # 保留コメントを出力
    $ annofabcli comment list --project_id prj1 --task_id task1 task2 \
     --comment_type onhold


デフォルトでは返信コメントも出力されます。返信コメントを除去する場合は、 ``--exclude_reply`` を指定してください。

.. code-block::

    $ annofabcli comment list --project_id prj1 --task_id task1 task2 \
     --exclude_reply




出力結果
=================================


JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli comment list --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
    {
        "project_id": "project1",
        "task_id": "task1",
        "input_data_id": "input_data1",
        "comment_id": "comment1",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "account1",
        "comment_type": "onhold",
        "phrases": [],
        "phrase_names_en": [],
        "phrase_names_ja": [],
        "comment": "画像が間違っている",
        "comment_node": {
            "data": null,
            "annotation_id": "8ec9417b-abef-47ad-af7d-e0a03c680eac",
            "label_id": "8ec9417b-abef-47ad-af7d-e0a03c680eac",
            "label_name_en": "car",
            "label_name_ja": "自動車",
            "status": "open",
            "_type": "Root"
        },
        "datetime_for_sorting": "2022-07-05T11:45:21.968+09:00",
        "created_datetime": "2022-07-05T11:45:32.88+09:00",
        "updated_datetime": "2022-07-05T11:45:32.88+09:00",
        "reply_count": 1
    },
    {
        "project_id": "project1",
        "task_id": "task1",
        "input_data_id": "input_data1",
        "comment_id": "comment2",
        "phase": "acceptance",
        "phase_stage": 1,
        "account_id": "account2",
        "comment_type": "inspection",
        "phrases": [],
        "phrase_names_en": [],
        "phrase_names_ja": [],
        "comment": "枠がずれています",
        "comment_node": {
            "data": {
                "x": 62,
                "y": 137,
                "_type": "Point"
            },
            "annotation_id": "8ec9417b-abef-47ad-af7d-e0a03c680eac",
            "label_id": "8ec9417b-abef-47ad-af7d-e0a03c680eac",
            "label_name_en": "car",
            "label_name_ja": "自動車",
            "status": "open",
            "_type": "Root"
        },
        "datetime_for_sorting": "2022-07-05T11:45:08.506+09:00",
        "created_datetime": "2022-07-05T11:45:32.88+09:00",
        "updated_datetime": "2022-07-05T11:45:32.88+09:00",
        "reply_count": 0
    }
    ]




Usage Details
=================================

.. argparse::
    :ref: annofabcli.comment.list_comment.add_parser
    :prog: annofabcli comment list
    :nosubcommands:
    :nodefaultconst:
