===========================
task_count list_by_metadata
===========================

Description
=================================

タスクメタデータごとに、フェーズと状態別のタスク数などを横持ちのCSV形式で出力します。
集計列の意味は :doc:`list_by_task_id_group` と同じです。


Examples
=================================

1つのメタデータでグループ化
---------------------------------

``--metadata_key`` に、集計対象のタスクメタデータキーを指定します。
指定したメタデータが存在しないタスクも、値が空欄のグループとして出力します。

.. code-block:: console

    $ annofabcli task_count list_by_metadata --project_id prj1 \
        --metadata_key dataset_type --output out.csv

出力ファイル :file:`out.csv` の内容は次のとおりです。

.. csv-table:: out.csv
   :header: metadata.dataset_type,annotation.never_worked,annotation.worked,annotation.on_hold,inspection.never_worked,inspection.worked,inspection.on_hold,acceptance.never_worked,acceptance.worked,acceptance.on_hold,acceptance.complete

   train,10,20,1,5,12,0,3,8,1,40
   validation,2,6,0,1,4,0,1,3,0,13
   ,1,0,0,0,0,0,0,0,0,0


複数のメタデータでグループ化
---------------------------------

複数のキーを指定すると、指定したメタデータ値の組み合わせで集計します。

.. code-block:: console

    $ annofabcli task_count list_by_metadata --project_id prj1 \
        --metadata_key dataset_type location --output out.csv


入力データ数で集計
---------------------------------

``--unit input_data_count`` を指定すると、タスク数ではなく入力データ数を集計します。
``video_duration_hour`` または ``video_duration_minute`` を指定すると、動画プロジェクトの動画時間を集計します。

.. code-block:: console

    $ annofabcli task_count list_by_metadata --project_id prj1 \
        --metadata_key dataset_type --unit input_data_count --output out.csv


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task_count.list_by_metadata.add_parser
   :prog: annofabcli task_count list_by_metadata
   :nosubcommands:
   :nodefaultconst:
