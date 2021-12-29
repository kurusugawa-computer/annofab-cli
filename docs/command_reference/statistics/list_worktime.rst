==========================================
statistics list_worktime
==========================================

Description
=================================

タスク履歴イベント全件ファイルから、日ごとユーザごとの作業時間の一覧を出力します。



Examples
=================================

基本的な使い方
--------------------------


.. code-block::

    $ annofabcli statistics list_worktime --project_id prj1




出力結果
=================================


.. code-block::

    $ annofabcli statistics list_worktime --project_id prj1 --output out.csv


.. csv-table:: out.csv
   :header: date,account_id,user_id,username,biography,worktime_hour,annotation_worktime_hour,inspection_worktime_hour,acceptance_worktime_hour

    2021-11-01,alice,alice,Alice,U.S.,2.35,2.35,0,0.0
    2021-11-02,bob,bob,Bob,Japan,4.37,3.43,0,0.94


Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.list_worktime.add_parser
   :prog: annofabcli statistics list_worktime
   :nosubcommands:
   :nodefaultconst:
