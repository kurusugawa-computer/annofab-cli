==========================================
inspection_comment list
==========================================

Description
=================================
検査コメントの一覧を出力します。


.. warning::

    非推奨なコマンドです。2022/12/01以降に廃止する予定です。
    替わりに `annofabcli comment list <../comment/list.html>`_ コマンドを使用してください。


Examples
=================================

基本的な使い方
--------------------------

``--task_id`` に出力対象のタスクのtask_idを指定してください。

.. code-block::

    $ annofabcli inspection_comment list --project_id prj1 --task_id task1 task2



絞り込み
--------------------------
デフォルトでは指摘に対する返信コメントも出力します。返信コメントを除外する場合は、``--exclude_reply`` を指定してください。自分自身が所属していて、進行中のプロジェクトが対象になります。

.. code-block::

    $ annofabcli inspection_comment list --project_id prj1 --task_id task1 task2 --exclude_reply


返信コメントのみ出力する場合は、``--only_reply`` を指定してください。

.. code-block::

    $ annofabcli inspection_comment list --project_id prj1 --task_id task1 task2 --only_reply




出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli inspection_comment list --project_id prj1 --task_id task1 \
     --format csv --output out.csv

`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/inspection_comment/list/out.csv>`_

JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli inspection_comment list --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
        {
            "project_id": "prj1",
            "task_id": "task1",
            "input_data_id": "input1",
            "inspection_id": "inspection1",
            "phase": "annotation",
            "phase_stage": 1,
            "commenter_account_id": "account1",
            "annotation_id": null,
            "label_id": null,
            "data": {
            "x": 0,
            "y": 0,
            "_type": "Point"
            },
            "parent_inspection_id": null,
            "phrases": [],
            "comment": "test-comment",
            "status": "no_correction_required",
            "created_datetime": "2020-09-09T15:23:12.802+09:00",
            "updated_datetime": "2020-09-09T15:23:13.18+09:00",
            "commenter_user_id": "user1",
            "commenter_username": "test-user1",
            "phrase_names_en": [],
            "phrase_names_ja": [],
            "label_name_en": null,
            "label_name_ja": null,
            "input_data_index": 0
        },
        ...
    ]


Usage Details
=================================

.. argparse::
   :ref: annofabcli.inspection_comment.list_inspections.add_parser
   :prog: annofabcli inspection_comment list
   :nosubcommands:
   :nodefaultconst:


See also
=================================
* `annofabcli inspection_comment list_all <../inspection_comment/list_all.html>`_     


