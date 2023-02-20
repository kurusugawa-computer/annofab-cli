==========================================
task_history_event download
==========================================

Description
=================================
タスク履歴イベント全件ファイルをダウンロードします。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドを実行すると、タスク履歴イベント全件ファイルがダウンロードされます。
タスク履歴イベント全件ファイルのフォーマットについては https://annofab.com/docs/api/#section/TaskHistoryEvent を参照してください。

.. code-block::

    $ annofabcli task_history_event download --project_id prj1 --output task_history_event.json

タスク履歴イベントの状態は、02:00(JST)頃にタスク履歴イベント全件ファイルに反映されます。




.. code-block::

    $ annofabcli task_history_event download --output out.json
    $ jq . out.json > out-pretty.json


.. code-block::
    :caption: out-pretty.json

    [
        {
            "project_id": "prj1",
            "task_id": "task1",
            "task_history_id": "17724ca4-6cdd-4351-86e6-16c19d50233e",
            "created_datetime": "2021-05-20T13:37:52.281+09:00",
            "phase": "annotation",
            "phase_stage": 1,
            "status": "working",
            "account_id": "user1",
            "request": {
            "status": "working",
            "account_id": "user1",
            "last_updated_datetime": "2021-05-20T13:37:28.179+09:00",
            "force": false
            },
        },
        {
            "project_id": "prj1",
            "task_id": "task1",
            "task_history_id": "c22ec069-a6a9-42f9-8438-53bd6145b91f",
            "created_datetime": "2021-05-20T14:16:23.534+09:00",
            "phase": "annotation",
            "phase_stage": 1,
            "status": "on_hold",
            "account_id": "user1",
            "request": {
            "status": "on_hold",
            "account_id": "user1",
            "last_updated_datetime": "2021-05-20T13:37:52.296+09:00",
            "force": false
            },
        }
    ]


Usage Details
=================================

.. argparse::
    :ref: annofabcli.task_history_event.download_task_history_event_json.add_parser
    :prog: annofabcli task_history_event download
    :nosubcommands:
    :nodefaultconst:


