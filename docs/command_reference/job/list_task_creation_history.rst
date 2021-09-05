==========================================
job list_task_creation_history
==========================================

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
        "job_id": "gen-tasks:7af76c2b-b3c6-408e-84ba-25a598fc61fe",
        "job_status": "succeeded",
        "generated_task_count": 600,
        "created_datetime": "2021-09-02T13:30:46.432+09:00",
        "updated_datetime": "2021-09-02T13:31:37.475+09:00",
        "task_generated_rule": {
          "task_id_prefix": "2021-09-02",
          "input_data_count": 10,
          "allow_duplicate_input_data": false,
          "input_data_order": "name_asc",
          "_type": "ByCount"
        }
      },
      {
        "project_id": "prj1",
        "job_id": "gen-tasks:40acde7b-7165-4687-bf3f-72d1f4f60c51",
        "job_status": "succeeded",
        "generated_task_count": 200,
        "created_datetime": "2021-08-30T21:42:11.89+09:00",
        "updated_datetime": "2021-08-30T21:43:00.425+09:00",
        "task_generated_rule": {
          "task_id_prefix": "2021-08-30",
          "input_data_count": 10,
          "allow_duplicate_input_data": false,
          "input_data_order": "name_asc",
          "_type": "ByCount"
        }
      },
     ...
    ]


.. argparse::
   :ref: annofabcli.job.list_generated_task_history.add_parser
   :prog: annofabcli job list_task_creation_history
   :nosubcommands:
