====================================================================================
statistics summarize_task_count_by_task_id
====================================================================================

Description
=================================


task_idのプレフィックスごとに、タスク数をCSV形式で出力します。
task_idのプレフィックスは、task_idが ``{prefix}_{連番}`` のフォーマットに従っていることを前提としています。




Examples
=================================

基本的な使い方
--------------------------


.. code-block::

    $ annofabcli statistics summarize_task_count_by_task_id --project_id prj1 




出力結果
=================================


.. code-block::

    $ annofabcli statistics summarize_task_count_by_task_id --project_id prj1 --output out.csv


.. csv-table:: out.csv
   :header: task_id_prefix,complete,on_hold,annotation_not_started,inspection_not_started,acceptance_not_started,other,sum
   
    202001,397,5,0,0,0,4,406
    202002,98,7,0,0,0,1,106
    202003,16,5,246,0,2,26,295


各列の内容は以下の通りです。

* complete: 完了状態のタスク数
* on_hold: 保留状態のタスク数
* annotation_not_started: 教師付フェーズが一度も作業されていないタスク数
* inspection_not_started: 検査フェーズが一度も作業されていないタスク数
* acceptance_not_started: 受入フェーズが一度も作業されていないタスク数
* other: 休憩中、作業中状態のタスク数
* sum: 合計のタスク数

