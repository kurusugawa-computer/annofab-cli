==========================================
task_history_event list_all
==========================================

Description
=================================

すべてのタスク履歴イベントの一覧を出力します。

.. note::

    出力されるタスク履歴イベントは、コマンドを実行した日の02:00(JST)頃の状態です。最新の情報を出力する方法はありません。


Examples
=================================


基本的な使い方
--------------------------

以下のコマンドは、すべてのタスク履歴イベントの一覧を出力します。

.. code-block::

    $ annofabcli task_history_event list_all --project_id prj1


`annofabcli task_history_event download <../task_history_event/download.html>`_ コマンドでダウンロードできるタスク履歴イベント全件ファイルから、タスク履歴イベントの一覧を出力することもできます。

.. code-block::

    $ annofabcli task_history_event download --project_id prj1 --output task_history_event.json 
    $ annofabcli task_history_event list_all --project_id prj1 --task_history_json task_history_event.json 



出力結果
=================================


CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli task_history_event list_all --project_id prj1 --format csv --output out.csv

`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/task_history_event/list_all/out.csv>`_


JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli task_history_event list_all --project_id prj1 --format pretty_json --output out.json



.. code-block::
    :caption: out.json

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
        "user_id": "user1",
        "username": "user1"
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
        "user_id": "user1",
        "username": "user1"
    }
    ]




Usage Details
=================================

.. argparse::
   :ref: annofabcli.task_history_event.list_all_task_history_event.add_parser
   :prog: annofabcli task_history_event list_all
   :nosubcommands:
   :nodefaultconst:


See also
=================================
* `annofabcli task_history_event list_all <../task_history_event/list_all.html>`_

