=====================
job list_task_creation_history
=====================

Description
=================================
タスクの作成履歴一覧を出力します。



Examples
=================================

基本的な使い方
--------------------------

以下のコマンドは、プロジェクトprj1のタスク作成履歴の一覧を出力します。

.. code-block::

    $ annofabcli job list_task_creation_history --project_id prj1




出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli job list_task_creation_history --project_id prj1  --format csv --output out.csv

`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/job/list_task_creation_history/out.csv>`_

JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli job list_task_creation_history --project_id prj1 --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
        {
            "project_id": "prj1",
            "job_type": "gen-annotation",
            "job_id": "12345678-abcd-1234-abcd-1234abcd5678",
            "job_status": "succeeded",
            "job_execution": null,
            "job_detail": null,
            "created_datetime": "2020-12-23T03:02:56.478+09:00",
            "updated_datetime": "2020-12-23T03:02:56.478+09:00"
        },
        ...
    ]


