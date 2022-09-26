=====================
task_history list
=====================

Description
=================================
タスク履歴の一覧を出力します。


Examples
=================================


基本的な使い方
--------------------------

``--task_id`` に出力対象のタスクのtask_idを指定してください。

.. code-block::

    $ annofabcli task_history list --project_id prj1 --task_id file://task_id.txt




出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli task_history list --project_id prj1 --format csv --output out.csv

`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/task_history/list/out.csv>`_

JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli task_history list --project_id prj1 --format pretty_json --output out.json



.. code-block::
    :caption: out.json

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
            "user_id": null,
            "username": null,
            "worktime_hour": 0.0
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
            "user_id": null,
            "username": null,
            "worktime_hour": 0.0
            },
            ...
        ],
    }

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task_history.list_task_history.add_parser
   :prog: annofabcli task_history list
   :nosubcommands:
   :nodefaultconst:

See also
=================================
* `annofabcli task_history list_all <../task_history/list_all.html>`_

