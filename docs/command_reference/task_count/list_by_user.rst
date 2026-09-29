=======================
task_count list_by_user
=======================

Description
=================================

ユーザごとに、担当しているタスク数や入力データ数などをCSV形式で出力します。


Examples
=================================

基本的な使い方
--------------------------

.. code-block:: console

    $ annofabcli task_count list_by_user --project_id prj1 --output out.csv

出力ファイル :file:`out.csv` の内容は次のとおりです。

.. csv-table:: out.csv
   :header: user_id,username,biography,annotation.never_worked,annotation.worked,annotation.on_hold,inspection.never_worked,inspection.worked,inspection.on_hold,acceptance.never_worked,acceptance.worked,acceptance.on_hold,acceptance.complete

   unassigned,,,1,0,0,0,0,0,0,0,0,0
   user1,user1,,2,10,1,3,20,0,0,0,0,100
   user2,user2,,1,5,0,2,10,1,0,0,0,40

各列の内容は以下のとおりです。

フェーズごとに、``never_worked``（未着手）、``worked``（作業済み）、``on_hold``（保留中）のタスク数を出力します。
完了したタスクは ``acceptance.complete`` に出力します。
``never_worked`` の判定方法は :doc:`list_by_phase` と同じです。

担当者が割り当てられていないタスクは、``user_id`` が ``unassigned`` の行に集計します。
したがって、状態別の列をすべて合計すると、登録されているタスクの合計になります。


タスクメタデータでグループ化
---------------------------------

``--metadata_key`` でタスクメタデータのキーを指定すると、ユーザと指定したメタデータの値ごとにタスク数を集計します。
複数のキーも指定できます。指定したメタデータが存在しないタスクも、値が空欄のグループとして出力します。

.. code-block:: console

    $ annofabcli task_count list_by_user --project_id prj1 --metadata_key dataset_type --output out.csv

出力ファイル :file:`out.csv` の内容は次のとおりです。

.. csv-table:: out.csv
   :header: user_id,username,biography,metadata.dataset_type,annotation.never_worked,annotation.worked,annotation.on_hold,inspection.never_worked,inspection.worked,inspection.on_hold,acceptance.never_worked,acceptance.worked,acceptance.on_hold,acceptance.complete

   user1,user1,,train,1,8,0,0,10,0,0,0,0,100
   user1,user1,,validation,0,2,0,0,5,0,0,0,0,20


入力データ数で集計
---------------------------------

``--unit input_data_count`` を指定すると、タスク数ではなく入力データ数を集計します。
``video_duration_hour`` または ``video_duration_minute`` を指定すると、動画プロジェクトの動画時間を集計します。

.. code-block:: console

    $ annofabcli task_count list_by_user --project_id prj1 \
        --unit input_data_count --output out.csv


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task_count.list_by_user.add_parser
   :prog: annofabcli task_count list_by_user
   :nosubcommands:
   :nodefaultconst:
