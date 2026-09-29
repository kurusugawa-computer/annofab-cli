===================================
task_count list_by_task_id_group
===================================

Description
=================================

タスクIDのグループごとに、フェーズと状態別のタスク数などを横持ちのCSV形式で出力します。

``never_worked.unassigned`` と ``never_worked.assigned`` は ``never_worked`` に、
``worked.not_rejected`` と ``worked.rejected`` は ``worked`` にまとめます。
完了したタスクは ``acceptance.complete`` に集計します。


Examples
=================================

タスクIDのプレフィックスでグループ化
-----------------------------------------

``--task_id_delimiter`` に、タスクIDのプレフィックスと連番を分ける区切り文字を指定します。
たとえば、区切り文字が ``_`` の場合、タスクID ``aa_bb_001`` のグループは ``aa_bb`` です。

.. code-block:: console

    $ annofabcli task_count list_by_task_id_group --project_id prj1 --task_id_delimiter _ --output out.csv

出力ファイル :file:`out.csv` の内容は次のとおりです。

.. csv-table:: out.csv
   :header: task_id_group,annotation.never_worked,annotation.worked,annotation.on_hold,inspection.never_worked,inspection.worked,inspection.on_hold,acceptance.never_worked,acceptance.worked,acceptance.on_hold,acceptance.complete,total

   train,10,20,1,5,12,0,3,8,1,40,100
   validation,2,6,0,1,4,0,1,3,0,13,30


タスクIDとグループを個別に指定
-----------------------------------------

``--task_id_groups`` に、タスクIDグループをキー、タスクIDのリストを値とするJSON文字列を指定します。
どのグループにも指定されていないタスクは ``unknown`` に集計されます。

.. code-block:: console

    $ annofabcli task_count list_by_task_id_group --project_id prj1 \
        --task_id_groups '{"group1":["id1","id2"],"group2":["id3","id4"]}' \
        --output out.csv


入力データ数で集計
-----------------------------------------

``--unit input_data_count`` を指定すると、タスク数ではなく入力データ数を集計します。
``video_duration_hour`` または ``video_duration_minute`` を指定すると、動画プロジェクトの動画時間を集計します。
``total`` 列も、``--unit`` に指定した単位で集計します。

.. code-block:: console

    $ annofabcli task_count list_by_task_id_group --project_id prj1 --task_id_delimiter _ \
        --unit input_data_count --output out.csv


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task_count.list_by_task_id_group.add_parser
   :prog: annofabcli task_count list_by_task_id_group
   :nosubcommands:
   :nodefaultconst:
