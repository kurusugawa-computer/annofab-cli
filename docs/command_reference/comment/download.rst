==========================================
comment download
==========================================

Description
=================================
コメント全件ファイルをダウンロードします。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドを実行すると、コメント全件ファイルがダウンロードされます。

.. code-block::

    $ annofabcli comment download --project_id prj1 --output comment.json

作成したコメントは、02:00(JST)頃にコメント全件ファイルに反映されます。



出力結果
=================================


.. code-block::

    $ annofabcli comment download --output out.json
    $ jq . out.json > out-pretty.json


.. code-block::
    :caption: out-pretty.json

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
        "comment": "画像が間違っている",
        "comment_node": {
        "data": null,
        "annotation_id": "8ec9417b-abef-47ad-af7d-e0a03c680eac",
        "label_id": "8ec9417b-abef-47ad-af7d-e0a03c680eac",
        "status": "open",
        "_type": "Root"
        },
        "datetime_for_sorting": "2022-07-05T11:45:21.968+09:00",
        "created_datetime": "2022-07-05T11:45:32.88+09:00",
        "updated_datetime": "2022-07-05T11:45:32.88+09:00"
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
        "comment": "枠がずれています",
        "comment_node": {
        "data": {
            "x": 62,
            "y": 137,
            "_type": "Point"
        },
        "annotation_id": "8ec9417b-abef-47ad-af7d-e0a03c680eac",
        "label_id": "8ec9417b-abef-47ad-af7d-e0a03c680eac",
        "status": "open",
        "_type": "Root"
        },
        "datetime_for_sorting": "2022-07-05T11:45:08.506+09:00",
        "created_datetime": "2022-07-05T11:45:32.88+09:00",
        "updated_datetime": "2022-07-05T11:45:32.88+09:00"
    }
    ]



Usage Details
=================================

.. argparse::
    :ref: annofabcli.comment.download_comment_json.add_parser
    :prog: annofabcli comment download
    :nosubcommands:
    :nodefaultconst:


