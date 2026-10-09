=======================
task_count list_by_user
=======================

Description
=================================

ユーザごとに、担当しているタスク数や入力データ数などをCSVまたはJSON形式で出力します。


Examples
=================================

基本的な使い方
--------------------------

.. code-block:: console

    $ annofabcli task_count list_by_user --project_id prj1 --output out.csv

出力ファイル :file:`out.csv` の内容は次のとおりです。

.. csv-table:: out.csv
   :file: list_by_user/out.csv
   :header-rows: 1

各列の内容は以下のとおりです。

フェーズごとに、``never_worked``（未着手）、``worked``（作業済み）、``on_hold``（保留中）のタスク数を出力します。
完了したタスクは ``acceptance.complete`` に出力します。
``never_worked`` の判定方法は :doc:`list_by_phase` と同じです。

担当者が割り当てられていないタスクは、``user_id`` が ``unassigned`` の行に集計します。
したがって、状態別の列をすべて合計すると、登録されているタスクの合計になります。


タスクメタデータでグループ化
---------------------------------

``--metadata_key`` でタスクメタデータのキーを指定すると、ユーザと指定したメタデータの値ごとにタスク数を集計します。
複数のキーも指定できます。指定したメタデータが存在しないタスクも、値が空欄のグループとして出力します。

.. code-block:: console

    $ annofabcli task_count list_by_user --project_id prj1 --metadata_key dataset_type --output out.csv

出力ファイル :file:`out.csv` の内容は次のとおりです。

.. csv-table:: out_2.csv
   :file: list_by_user/out_2.csv
   :header-rows: 1


入力データ数で集計
---------------------------------

``--unit input_data_count`` を指定すると、タスク数ではなく入力データ数を集計します。
``video_duration_hour`` または ``video_duration_minute`` を指定すると、動画プロジェクトの動画時間を集計します。

.. code-block:: console

    $ annofabcli task_count list_by_user --project_id prj1 \
        --unit input_data_count --output out.csv


JSON形式で出力
---------------------------------

``--format json`` または ``--format pretty_json`` を指定すると、CSVと同じ列名をキーにした
オブジェクトの配列を出力します。欠損値は ``null``、空の集計結果は ``[]`` になります。
省略時はCSV形式で出力します。

.. code-block:: console

    $ annofabcli task_count list_by_user --project_id prj1 --format pretty_json --output out.json

出力例（先頭の1行分）は次のとおりです。

.. code-block:: json

    [
      {
        "user_id": "unassigned",
        "username": null,
        "biography": null,
        "annotation.never_worked": 1,
        "annotation.worked": 0,
        "annotation.on_hold": 0,
        "inspection.never_worked": 0,
        "inspection.worked": 0,
        "inspection.on_hold": 0,
        "acceptance.never_worked": 0,
        "acceptance.worked": 0,
        "acceptance.on_hold": 0,
        "acceptance.complete": 0
      }
    ]


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task_count.list_by_user.add_parser
   :prog: annofabcli task_count list_by_user
   :nosubcommands:
   :nodefaultconst:
