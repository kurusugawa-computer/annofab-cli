=========================
task_count list_by_phase
=========================

Description
=================================
フェーズごとのタスク数を出力します。

タスクの状態は以下の6つのカテゴリに分類されます。

* ``never_worked.unassigned``: 下記の「作業していない」の条件に一致し、担当者未割り当て
* ``never_worked.assigned``: 下記の「作業していない」の条件に一致し、担当者割り当て済み
* ``worked.not_rejected``: 作業中・休憩中で現在のフェーズが差し戻しによる再実行ではないタスク、または「作業していない」の条件に一致しない未着手タスク
* ``worked.rejected``: 作業中・休憩中で、現在のフェーズが差し戻しによる再実行となっているタスク
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

「作業していない」とみなすのは、以下の条件をすべて満たすタスクです。

* 未着手状態である
* 現在のフェーズが差し戻しによる再実行ではない
* 現在のフェーズの累計作業時間が ``--not_worked_threshold_second`` に指定した秒数以下である

閾値のデフォルトは0秒です。作業中・休憩中・保留中・完了状態のタスクには、この閾値を適用しません。

.. code-block::

    $ annofabcli task_count list_by_phase --project_id prj1 --not_worked_threshold_second 60 --output out.csv


この例では、上記の状態・フェーズの条件を満たし、現在のフェーズの累計作業時間が60秒以下のタスクを
``never_worked.assigned`` または ``never_worked.unassigned`` に分類します。
差し戻し後の未着手タスクは、作業時間にかかわらず ``worked.not_rejected`` に分類します。




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
   :ref: annofabcli.task_count.list_by_phase.create_parser
   :prog: annofabcli task_count list_by_phase
   :nosubcommands:
   :nodefaultconst:
