==========================================
statistics list_by_date_user
==========================================

Description
=================================

タスク数や作業時間などの情報を、日ごとユーザごとに出力します。



Examples
=================================

基本的な使い方
--------------------------

タスク履歴全件ファイルから、CSVファイルを出力します。

.. code-block::

    $ annofabcli statistics list_by_date_user --project_id prj1

集計期間を指定することも可能です。

.. code-block::

    $ annofabcli statistics list_by_date_user --project_id prj1 \
    --start_date 2020-01-01 --end_date 2020-01-31




出力結果
=================================


.. code-block::

    $ annofabcli statistics list_by_date_user --project_id prj1 --output out.csv


.. csv-table:: out.csv
   :header: date,user_id,username,biography,worktime_hour,annotation_submitted_task_count,inspection_submitted_task_count,acceptance_submitted_task_count,rejected_task_count


    2020-12-15,user1,user1,,3.844,28,0,0,4
    2020-12-16,user1,user2,,1.047,0,0,16,1
    2020-12-16,user2,user3,,2.834,0,0,6



各列の詳細は以下の通りです。

* worktime_hour: 作業時間[hour]
* annotation_submitted_task_count: 教師付フェーズのタスクを提出した回数
* inspection_submitted_task_count: 検査フェーズのタスクを差し戻しまたは合格にしたした回数
* acceptance_submitted_task_count: 受入フェーズのタスクを差し戻しまたは合格にしたした回数
* rejected_task_count: 差し戻された回数


.. warning::

    以下の数値は直感的でない値になる場合があります。信用しないでください。

    * annotation_submitted_task_count
    * inspection_submitted_task_count
    * acceptance_submitted_task_count
    * rejected_task_count

    

    
