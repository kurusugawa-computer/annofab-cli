==========================================
task_history download
==========================================

Description
=================================
タスク履歴全件ファイルをダウンロードします。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドを実行すると、タスク履歴全件ファイルがダウンロードされます。
タスク履歴全件ファイルのフォーマットについては https://annofab.com/docs/api/#section/TaskHistory を参照してください。

.. code-block::

    $ annofabcli task_history download --project_id prj1 --output task_history.json

タスク履歴の状態は、02:00(JST)頃にタスク履歴全件ファイルに反映されます。


出力結果
=================================


.. code-block::

    $ annofabcli task_history download --output out.json
    $ jq . out.json > out-pretty.json


.. code-block::
    :caption: out-pretty.json

    {
        "task1": [
            {
            "project_id": "prj1",
            "task_id": "task1",
            "task_history_id": "12345678-abcd-1234-abcd-1234abcd5678",
            "started_datetime": "2020-12-09T02:17:42.257+09:00",
            "ended_datetime": null,
            "accumulated_labor_time_milliseconds": "PT0S",
            "phase": "annotation",
            "phase_stage": 1,
            "account_id": null,
            },
            ...
        ],
        "task2": [
            {
            "project_id": "prj1",
            "task_id": "task2",
            "task_history_id": "22345678-abcd-1234-abcd-1234abcd5678",
            "started_datetime": "2020-12-09T02:17:42.257+09:00",
            "ended_datetime": null,
            "accumulated_labor_time_milliseconds": "PT0S",
            "phase": "annotation",
            "phase_stage": 1,
            "account_id": null,
            },
            ...
        ],


Usage Details
=================================

.. argparse::
    :ref: annofabcli.task_history.download_task_history_json.add_parser
    :prog: annofabcli task_history download
    :nosubcommands:
    :nodefaultconst:


