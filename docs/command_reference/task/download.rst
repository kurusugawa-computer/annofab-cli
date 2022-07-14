==========================================
task download
==========================================

Description
=================================
タスク全件ファイルをダウンロードします。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドを実行すると、タスク全件ファイルがダウンロードされます。
タスク全件ファイルのフォーマットについては https://annofab.com/docs/api/#section/Task を参照してください。

.. code-block::

    $ annofabcli task download --project_id prj1 --output task.json

タスクの状態は、02:00(JST)頃にタスク全件ファイルに反映されます。
現在のタスクの状態をタスク全件ファイルに反映させたい場合は、``--latest`` を指定してください。
タスク全件ファイルへの反映が完了したら、ダウンロードされます。
ただし、データ数に応じて数分から数十分待ちます。


.. code-block::

    $ annofabcli task download --project_id prj1 --output task.json --latest


出力結果
=================================


.. code-block::

    $ annofabcli task download --output out.json
    $ jq . out.json > out-pretty.json


.. code-block::
    :caption: out-pretty.json

    [
      {
        "project_id": "prj1",
        "task_id": "task1",
        "phase": "acceptance",
        "phase_stage": 1,
        "status": "complete",
        "input_data_id_list": [
          "input1"
        ],
        "account_id": "12345678-abcd-1234-abcd-1234abcd5678",
        "histories_by_phase": [
          {
            "account_id": "12345678-abcd-1234-abcd-1234abcd5678",
            "phase": "annotation",
            "phase_stage": 1,
            "worked": true,
          },
          ...
        ],
        "work_time_span": 8924136,
        "started_datetime": "2020-11-24T16:21:27.753+09:00",
        "updated_datetime": "2020-11-24T16:29:29.381+09:00",
        "operation_updated_datetime": "2020-11-24T16:29:29.381+09:00",
        "sampling": null,
        "metadata": {},
      },
      ...
    ]


Usage Details
=================================

.. argparse::
    :ref: annofabcli.task.download_task_json.add_parser
    :prog: annofabcli task download
    :nosubcommands:
    :nodefaultconst:


