==========================================
task_history_event list_worktime
==========================================

Description
=================================
タスク履歴イベントから作業時間の一覧を出力します。
「作業中状態から休憩状態までの作業時間」など、タスク履歴より詳細な作業時間の情報を出力します。

日ごとユーザーごとの作業時間を確認する場合は、 `annofabcli statistics list_worktime <../statistics/list_worktime.html>`_ を参照してください。


Examples
=================================


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
            "status": "complete"
        },
        "end_event_request": {
            "status": "complete",
            "force": false,
            "account_id": "user1",
            "user_id": "user1",
            "username": "user1"
        }
            
    }
    ]

出力結果の主要な項目の説明
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

* ``worktime_hour`` : 作業時間（単位は時間）
* ``start_event`` : 作業開始イベントの情報

  * ``task_history_id`` : 作業開始イベントのID
  * ``created_datetime`` : 作業開始イベントの作成日時
  * ``status`` : 作業開始イベントのステータス。常に ``working`` です。

* ``end_event`` : 作業終了イベントの情報

  * ``task_history_id`` : 作業終了イベントのID
  * ``created_datetime`` : 作業終了イベントの作成日時
  * ``status`` : 作業終了イベントのステータス。 ``complete`` , ``break`` , ``on_hold`` のいずれかです。

* ``end_event_request`` : 作業終了イベントが発行された ``operateTask`` APIのリクエスト情報

  * ``status`` : タスクのステータス
  * ``force`` : 強制操作（強制差し戻しなど）かどうか
  * ``account_id``, ``user_id``, ``username`` : 担当者のユーザー情報



CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli task_history_event list_worktime --project_id prj1 --output out.csv


.. csv-table:: out.csv 
    :header-rows: 1
    :file: list_worktime/out.csv




Usage Details
=================================

.. argparse::
   :ref: annofabcli.task_history_event.list_worktime.add_parser
   :prog: annofabcli task_history_event list_worktime
   :nosubcommands:
   :nodefaultconst:

