=======================
task_count list_by_user
=======================

Description
=================================

ユーザごとに、担当しているタスク数をCSV形式で出力します。


Examples
=================================

基本的な使い方
--------------------------

.. code-block:: console

    $ annofabcli task_count list_by_user --project_id prj1 --output out.csv

出力ファイル :file:`out.csv` の内容は次のとおりです。

.. csv-table:: out.csv
   :header: user_id,username,biography,annotation_not_started,inspection_not_started,acceptance_not_started,working,break,on_hold,complete

   user1,user1,,1,0,0,0,1,10,203
   user2,user2,,1,0,0,0,1,2,66

各列の内容は以下のとおりです。

* ``annotation_not_started``: 教師付フェーズが一度も作業されていないタスク数
* ``inspection_not_started``: 検査フェーズが一度も作業されていないタスク数
* ``acceptance_not_started``: 受入フェーズが一度も作業されていないタスク数
* ``working``: 作業中状態のタスク数
* ``break``: 休憩中状態のタスク数
* ``on_hold``: 保留中状態のタスク数
* ``complete``: 完了状態のタスク数


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task_count.list_by_user.add_parser
   :prog: annofabcli task_count list_by_user
   :nosubcommands:
   :nodefaultconst:
