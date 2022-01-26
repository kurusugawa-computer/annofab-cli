==========================================
task_history_event list_worktime
==========================================

Description
=================================
タスク履歴イベントから作業時間の一覧を出力します。
「作業中状態から休憩状態までの作業時間」など、タスク履歴より詳細な作業時間の情報を出力します。



Examples
=================================

基本的な使い方
--------------------------


.. code-block::

    $ annofabcli task_history_event list_worktime --project_id prj1 --output out.csv




出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli task_history_event list_worktime --project_id prj1 --output out.csv

`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/task_history_event/list_worktime/out.csv>`_



JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli task_history_event list_worktime --project_id prj1 --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
    {
        "project_id": "prj1",
        "task_id": "task1",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": "user1",
        "user_id": "user1",
        "username": "user1",
        "worktime_hour": 0.6420147222222222,
        "start_event": {
            "task_history_id": "17724ca4-6cdd-4351-86e6-16c19d50233e",
            "created_datetime": "2021-05-20T13:37:52.281+09:00",
            "status": "working"
        },
        "end_event": {
            "task_history_id": "c22ec069-a6a9-42f9-8438-53bd6145b91f",
            "created_datetime": "2021-05-20T14:16:23.534+09:00",
            "status": "on_hold"
        }
    },
    {
        "project_id": "prj1",
        "task_id": "task1",
        "phase": "annotation",
        "phase_stage": 1,
        "account_id": "user1",
        "user_id": "user1",
        "username": "user1",
        "worktime_hour": 0.02437027777777778,
        "start_event": {
            "task_history_id": "02d7dd4f-5c8c-4182-b6e8-cdf10b5be4ab",
            "created_datetime": "2021-06-08T17:51:41.218+09:00",
            "status": "working"
        },
        "end_event": {
            "task_history_id": "dfa073bd-6fe1-429f-9e65-d7062a64907d",
            "created_datetime": "2021-06-08T17:53:08.951+09:00",
            "status": "complete"
        }
    }
    ]

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task_history_event.list_worktime.add_parser
   :prog: annofabcli task_history_event list_worktime
   :nosubcommands:
   :nodefaultconst:

