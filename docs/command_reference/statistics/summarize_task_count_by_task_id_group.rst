====================================================================================
statistics summarize_task_count_by_task_id_group
====================================================================================

Description
=================================

task_idのグループごとにタスク数を集計します。




Examples
=================================

基本的な使い方
--------------------------

task_idのプレフィックスでグループ化する場合は、``--task_id_delimiter`` に区切り文字を指定してください。
たとえば ``--task_id_delimiter _`` を指定した場合、 task_id ``aa_bb_001`` のtask_id_groupは ``aa_bb`` になります。

.. code-block::

    $ annofabcli statistics summarize_task_count_by_task_id_group --project_id prj1 --task_id_delimiter "_"


task_idとtask_id_groupを個別に指定する場合は、 ``--task_id_group`` に ``{"group1":["id1","id2"], "group2":["id3","id4"]}`` のようなJSON文字列を指定してください。


.. code-block::

    $ annofabcli statistics summarize_task_count_by_task_id_group --project_id prj1 \
     --task_id_group '{"group1":["id1","id2"], "group2":["id3","id4"]}''


出力結果
=================================


.. code-block::

    $ annofabcli statistics summarize_task_count_by_task_id_group --project_id prj1 --output out.csv


.. csv-table:: out.csv
   :header: task_id_group,complete,on_hold,annotation_not_started,inspection_not_started,acceptance_not_started,other,sum
   
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

Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.summarize_task_count_by_task_id_group.add_parser
   :prog: annofabcli statistics summarize_task_count_by_task_id_group
   :nosubcommands:
   :nodefaultconst:
