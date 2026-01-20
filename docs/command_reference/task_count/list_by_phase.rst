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


.. csv-table::
   :header: phase,never_worked.unassigned,never_worked.assigned,worked.not_rejected,worked.rejected,on_hold,complete

   annotation,10,5,8,2,1,74
   inspection,0,0,12,3,0,85
   acceptance,0,0,8,0,0,92



メタデータキーでグループ化
--------------------------

``--metadata_key`` でメタデータのキーを指定すると、そのキーの値でグループ化して集計します。


.. code-block::

    $ annofabcli task_count list_by_phase --project_id prj1 --metadata_key dataset_type --output out.csv


.. csv-table::
   :header: phase,metadata.dataset_type,never_worked.unassigned,never_worked.assigned,worked.not_rejected,worked.rejected,on_hold,complete

   annotation,train,8,3,5,1,1,42
   annotation,validation,2,2,3,1,0,32
   inspection,train,0,0,8,2,0,48
   inspection,validation,0,0,4,1,0,37
   acceptance,train,0,0,5,0,0,53
   acceptance,validation,0,0,3,0,0,39



入力データ数で集計
--------------------------

``--unit input_data_count`` を指定すると、タスク数ではなく入力データ数で集計します。

.. code-block::

    $ annofabcli task_count list_by_phase --project_id prj1 --unit input_data_count --output out.csv

.. csv-table::
   :header: phase,never_worked.unassigned,never_worked.assigned,worked.not_rejected,worked.rejected,on_hold,complete

   annotation,15,8,12,3,2,110
   inspection,0,0,18,5,0,127
   acceptance,0,0,12,0,0,138


動画の長さ（時間）で集計
--------------------------

``--unit video_duration_hour`` を指定すると、動画プロジェクトにおいて動画の長さ（時間単位）で集計します。
このオプションは動画プロジェクトでのみ使用できます。

.. code-block::

    $ annofabcli task_count list_by_phase --project_id prj1 --unit video_duration_hour --output out.csv


.. csv-table::
   :header: phase,never_worked.unassigned,never_worked.assigned,worked.not_rejected,worked.rejected,on_hold,complete

   annotation,2.5,1.8,3.2,0.6,0.4,18.5
   inspection,0,0,4.2,1.1,0,22.7
   acceptance,0,0,2.8,0,0,27.2


作業時間の閾値を指定
--------------------------

``--not_worked_threshold_second`` を指定すると、指定した秒数以下の作業時間のタスクを「作業していない」とみなします。
デフォルトは0秒です。

.. code-block::

    $ annofabcli task_count list_by_phase --project_id prj1 --not_worked_threshold_second 60 --output out.csv


この例では、60秒以下の作業時間のタスクは ``never_worked.assigned`` または ``never_worked.unassigned`` に分類されます。




Usage Details
=================================

.. argparse::
   :ref: annofabcli.task_count.list_by_phase.add_parser
   :prog: annofabcli task_count list_by_phase
   :nosubcommands:
   :nodefaultconst:
