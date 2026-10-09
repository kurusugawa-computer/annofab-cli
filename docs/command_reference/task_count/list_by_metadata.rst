===========================
task_count list_by_metadata
===========================

Description
=================================

タスクメタデータごとに、フェーズと状態別のタスク数などを横持ちのCSVまたはJSON形式で出力します。
集計列の意味は :doc:`list_by_task_id_group` と同じです。


Examples
=================================

1つのメタデータでグループ化
---------------------------------

``--metadata_key`` に、集計対象のタスクメタデータキーを指定します。
指定したメタデータが存在しないタスクも、値が空欄のグループとして出力します。

.. code-block:: console

    $ annofabcli task_count list_by_metadata --project_id prj1 \
        --metadata_key dataset_type --output out.csv

出力ファイル :file:`out.csv` の内容は次のとおりです。

.. csv-table:: out.csv
   :file: list_by_metadata/out.csv
   :header-rows: 1


複数のメタデータでグループ化
---------------------------------

複数のキーを指定すると、指定したメタデータ値の組み合わせで集計します。

.. code-block:: console

    $ annofabcli task_count list_by_metadata --project_id prj1 \
        --metadata_key dataset_type location --output out.csv


入力データ数で集計
---------------------------------

``--unit input_data_count`` を指定すると、タスク数ではなく入力データ数を集計します。
``video_duration_hour`` または ``video_duration_minute`` を指定すると、動画プロジェクトの動画時間を集計します。

.. code-block:: console

    $ annofabcli task_count list_by_metadata --project_id prj1 \
        --metadata_key dataset_type --unit input_data_count --output out.csv


JSON形式で出力
---------------------------------

``--format json`` または ``--format pretty_json`` を指定すると、CSVと同じ列名をキーにした
オブジェクトの配列を出力します。欠損値は ``null``、空の集計結果は ``[]`` になります。
省略時はCSV形式で出力します。

.. code-block:: console

    $ annofabcli task_count list_by_metadata --project_id prj1 --metadata_key dataset_type --format pretty_json --output out.json

出力例（先頭の1行分）は次のとおりです。

.. code-block:: json

    [
      {
        "metadata.dataset_type": "train",
        "annotation.never_worked": 10,
        "annotation.worked": 20,
        "annotation.on_hold": 1,
        "inspection.never_worked": 5,
        "inspection.worked": 12,
        "inspection.on_hold": 0,
        "acceptance.never_worked": 3,
        "acceptance.worked": 8,
        "acceptance.on_hold": 1,
        "acceptance.complete": 40
      }
    ]


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task_count.list_by_metadata.add_parser
   :prog: annofabcli task_count list_by_metadata
   :nosubcommands:
   :nodefaultconst:
