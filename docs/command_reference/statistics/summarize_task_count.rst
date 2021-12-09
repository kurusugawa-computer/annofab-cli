==========================================
statistics summarize_task_count
==========================================

Description
=================================

タスクのフェーズ、ステータス、ステップごとにタスク数を、CSV形式で出力します。
「1回目の教師付」と「2回目の教師付」を区別して集計されます。


Examples
=================================

基本的な使い方
--------------------------


.. code-block::

    $ annofabcli statistics summarize_task_count --project_id prj1



出力結果
=================================


.. code-block::

    $ annofabcli statistics summarize_task_count --project_id prj1 --output out.csv


.. csv-table:: out.csv
   :header: step,phase,phase_stage,simple_status,task_count

    1,annotation,1,not_started,961
    1,annotation,1,working_break_hold,36
    1,inspection,1,not_started,72
    1,inspection,1,working_break_hold,1
    1,acceptance,1,not_started,205
    2,annotation,1,not_started,7
    2,inspection,1,not_started,2
    2,acceptance,1,not_started,1
    ,acceptance,1,complete,3791


各列の内容は以下の通りです。

* step：何回目のフェーズか
* simple_status：タスクステータスを簡略化したもの

  * not_started：未着手
  * working_break_hold：作業中か休憩中か保留中
  * complete：完了

「一度も作業されていない教師付未着手」のタスク数は、先頭行（step=1, phase=annotation, simple_status=not_started）のtask_countから分かります。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.summarize_task_count.add_parser
   :prog: annofabcli statistics summarize_task_count
   :nosubcommands:
   :nodefaultconst:
