==========================================
statistics list_labor_time_per_user
==========================================

Description
=================================

メンバ別の作業時間、完了数、差し戻し回数を日毎にCSV形式で出力する。






Examples
=================================

基本的な使い方
--------------------------


.. code-block::

    $ annofabcli statistics list_labor_time_per_user --project_id prj1





出力結果
=================================


.. code-block::

    $ annofabcli statistics list_labor_time_per_user --project_id prj1 --output out.csv



.. csv-table:: out.csv
   :header: date,account_id,user_id,username,biography,worktime_hour,tasks_completed,tasks_rejected

    2020-12-15,account1,user1,username1,,2.834,19,6
    2020-12-16,account1,user1,username1,,3.417,36,2
    2020-12-17,account2,user2,username2,,0.094,0,3



各列の詳細を以下に示します。

* worktime_hour: 作業時間[hour]
* tasks_completed: 完了したタスク数
* tasks_rejected: 差し戻された回数

.. warning::

    ``tasks_completed`` , ``tasks_rejected`` は直感的でない数字になる場合があります。信用しないでください。

.. argparse::
   :ref: annofabcli.statistics.list_labor_time_per_user.add_parser
   :prog: annofabcli statistics list_labor_time_per_user
   :nosubcommands:
