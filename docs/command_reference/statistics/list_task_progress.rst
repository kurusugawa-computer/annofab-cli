==========================================
statistics list_task_progress
==========================================

Description
=================================

タスク進捗状況をCSV形式で出力する。



Examples
=================================

基本的な使い方
--------------------------


.. code-block::

    $ annofabcli statistics list_task_progress --project_id prj1



出力結果
=================================


.. code-block::

    $ annofabcli statistics list_task_progress --project_id prj1 --output out.csv


.. csv-table:: out.csv
   :header: date,phase,status,count

    2020-12-15,annotation,break,1
    2020-12-15,annotation,not_started,59
    2020-12-15,annotation,on_hold,3
    2020-12-15,acceptance,not_started,29
    2020-12-15,acceptance,complete,8
    2020-12-16,annotation,not_started,50
    2020-12-16,acceptance,not_started,90
    2020-12-16,acceptance,complete,10

