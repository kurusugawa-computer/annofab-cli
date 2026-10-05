==========================================
task list_video_duration
==========================================

Description
=================================

タスクごとの動画長を出力します。入力データを共有するタスクも、それぞれ1件として出力します。
タスクで使われていない入力データは出力しません。

``task list`` と同じく、タスクの属性は ``phase`` 、 ``phase_stage`` 、 ``status`` で出力します。
``video_duration_second`` の単位は秒です。
入力データが見つからない場合や動画長が不明な場合は、JSONでは ``null`` 、CSVでは空欄になります。
JSONはタスクごとの平坦なオブジェクトの配列で、欠損時もキーを省略しません。
0件の場合はCSVのヘッダーのみ、JSONでは ``[]`` を出力します。
1タスクに入力データが1件ある動画タスクを対象にします。それ以外はエラーになります。

Examples
=================================

.. code-block:: bash

    $ annofabcli task list_video_duration --project_id prj1 --output out.csv
    $ annofabcli task list_video_duration --task_json task.json --input_data_json input_data.json \
        --task_id task1 task2 --format pretty_json --output out.json

出力結果
=================================

.. csv-table:: out.csv
   :header-rows: 1
   :file: list_video_duration/out.csv

.. code-block:: json

    [
      {
        "project_id": "project1",
        "task_id": "task1",
        "phase": "acceptance",
        "phase_stage": 1,
        "status": "complete",
        "input_data_id": "video1",
        "input_data_name": "video1.mp4",
        "video_duration_second": 10.0,
        "input_data_updated_datetime": "2024-10-04T09:18:02.416+09:00"
      },
      {
        "project_id": "project1",
        "task_id": "task2",
        "phase": "annotation",
        "phase_stage": 1,
        "status": "not_started",
        "input_data_id": "missing",
        "input_data_name": null,
        "video_duration_second": null,
        "input_data_updated_datetime": null
      }
    ]

分布の表示には :doc:`visualize_video_duration` を使用してください。

旧コマンドからの移行
=================================

:doc:`../statistics/list_video_duration` は非推奨です。
旧コマンドの ``task_phase`` 、 ``task_phase_stage`` 、 ``task_status`` は、
新コマンドでは ``phase`` 、 ``phase_stage`` 、 ``status`` になります。
旧コマンドは不明な動画長を0で出力しますが、新コマンドでは欠損値として出力します。
``input_data_updated_datetime`` は新コマンドでは常にJSONに含まれます。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.list_video_duration.add_parser
   :prog: annofabcli task list_video_duration
   :nosubcommands:
   :nodefaultconst:
