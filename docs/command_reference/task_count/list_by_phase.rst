=========================
task_count list_by_phase
=========================

Description
=================================
フェーズごとのタスク数を出力します。

タスクの状態は以下の6つのカテゴリに分類されます。

* ``never_worked.unassigned``: 一度も作業していない状態かつ担当者未割り当て
* ``never_worked.assigned``: 一度も作業していない状態かつ担当者割り当て済み
* ``worked.not_rejected``: 作業中または休憩中で、まだ差し戻されていない（次のフェーズに進んでいない）
* ``worked.rejected``: 作業中または休憩中で、差し戻された（次のフェーズに進んだ）
* ``on_hold``: 保留中
* ``complete``: 完了


Examples
=================================


基本的な使い方
--------------------------

以下のコマンドで、フェーズごとのタスク数を出力します。

.. code-block::

    $ annofabcli task_count list_by_phase --project_id prj1 --output out.csv


.. csv-table:: out.csv
   :file: list_by_phase/out.csv
   :header-rows: 1



メタデータキーでグループ化
--------------------------

``--metadata_key`` でメタデータのキーを指定すると、そのキーの値でグループ化して集計します。


.. code-block::

    $ annofabcli task_count list_by_phase --project_id prj1 --metadata_key dataset_type --output out.csv


.. csv-table:: out_2.csv
   :file: list_by_phase/out_2.csv
   :header-rows: 1



入力データ数で集計
--------------------------

``--unit input_data_count`` を指定すると、タスク数ではなく入力データ数で集計します。

.. code-block::

    $ annofabcli task_count list_by_phase --project_id prj1 --unit input_data_count --output out.csv

.. csv-table:: out_3.csv
   :file: list_by_phase/out_3.csv
   :header-rows: 1


動画の長さ（時間）で集計
--------------------------

``--unit video_duration_hour`` を指定すると、動画プロジェクトにおいて動画の長さ（時間単位）で集計します。
このオプションは動画プロジェクトでのみ使用できます。

.. code-block::

    $ annofabcli task_count list_by_phase --project_id prj1 --unit video_duration_hour --output out.csv


.. csv-table:: out_4.csv
   :file: list_by_phase/out_4.csv
   :header-rows: 1


作業時間の閾値を指定
--------------------------

``--not_worked_threshold_second`` を指定すると、指定した秒数以下の作業時間のタスクを「作業していない」とみなします。
デフォルトは0秒です。

.. code-block::

    $ annofabcli task_count list_by_phase --project_id prj1 --not_worked_threshold_second 60 --output out.csv


この例では、60秒以下の作業時間のタスクは ``never_worked.assigned`` または ``never_worked.unassigned`` に分類されます。




JSON形式で出力
---------------------------------

``--format json`` または ``--format pretty_json`` を指定すると、CSVと同じ列名をキーにした
オブジェクトの配列を出力します。欠損値は ``null``、空の集計結果は ``[]`` になります。
省略時はCSV形式で出力します。

.. code-block:: console

    $ annofabcli task_count list_by_phase --project_id prj1 --format pretty_json --output out.json

出力例（先頭の1行分）は次のとおりです。

.. code-block:: json

    [
      {
        "phase": "annotation",
        "never_worked.unassigned": 10,
        "never_worked.assigned": 5,
        "worked.not_rejected": 8,
        "worked.rejected": 2,
        "on_hold": 1,
        "complete": 74
      }
    ]


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task_count.list_by_phase.add_parser
   :prog: annofabcli task_count list_by_phase
   :nosubcommands:
   :nodefaultconst:
