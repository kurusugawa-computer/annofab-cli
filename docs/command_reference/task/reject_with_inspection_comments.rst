==========================================
task reject_with_inspection_comments
==========================================

Description
=================================
検査コメントを作成してから、そのコメントに紐付くタスクを差し戻します。

検査コメントを指定するJSONの形式は、 :doc:`../comment/create_inspection` の ``--json`` と同じです。
JSON内の ``task_id`` をもとに、差し戻すタスクを決定します。

Examples
=================================

基本的な使い方
--------------------------------------

以下のJSONは、アノテーションに紐付く検査コメントと、アノテーション漏れを指摘する検査コメントを表します。

.. code-block:: json
    :caption: inspection_comments.json

    [
        {
            "task_id": "task1",
            "input_data_id": "input_data1",
            "annotation_id": "annotation1",
            "comment": "属性値を確認してください。"
        },
        {
            "task_id": "task1",
            "input_data_id": "input_data2",
            "data": {"x": 100, "y": 200, "_type": "Point"},
            "comment": "人物のアノテーションがありません。追加してください。"
        }
    ]

以下のコマンドは、JSONに指定した検査コメントを作成した後、``task1`` を差し戻します。

.. code-block::

    $ annofabcli task reject_with_inspection_comments --project_id prj1 \
      --json file://inspection_comments.json

差し戻したタスクの担当者を指定する
--------------------------------------

``--assigned_annotator_user_id`` に担当させたいユーザのuser_idを指定できます。
担当者を割り当てない場合は、 ``--not_assign`` を指定してください。
どちらも指定しない場合は、最後の教師付フェーズを担当したユーザを割り当てます。

受入完了状態のタスクを差し戻す
--------------------------------------

受入完了状態のタスクを差し戻す場合は、 ``--cancel_acceptance`` を指定してください。

.. code-block::

    $ annofabcli task reject_with_inspection_comments --project_id prj1 \
      --json file://inspection_comments.json --cancel_acceptance

並列処理
--------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $ annofabcli task reject_with_inspection_comments --project_id prj1 \
      --json file://inspection_comments.json --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.reject_tasks_with_inspection_comments.add_parser
   :prog: annofabcli task reject_with_inspection_comments
