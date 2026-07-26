==========================================
タスクメタデータごとの生産性と品質.csv
==========================================

``--task_metadata_key`` を指定したときに出力されます。
たとえば ``--task_metadata_key category`` を指定した場合、 ``categoryごとの生産性と品質.csv`` が出力されます。

タスクの ``metadata`` に設定された値ごとに、生産性と品質が記載されています。
``metadata`` に指定キーが存在しない、または値が ``null`` のタスクは空欄として集計されます。

列の内容
===================================================================================================

先頭列には、 ``--task_metadata_key`` に指定したキー名が出力されます。
たとえば ``--task_metadata_key category`` を指定した場合、先頭列は ``category`` です。

主な列は以下の通りです。

* ``monitored_worktime_hour`` : 計測作業時間
* ``actual_worktime_hour`` : 実績作業時間。 ``monitored_worktime_hour`` とプロジェクト全体の計測作業時間/実績作業時間の比率から算出します。
* ``task_count`` : タスク数
* ``input_data_count`` : 入力データ数
* ``annotation_count`` : アノテーション数
* ``pointed_out_inspection_comment_count`` : 検査コメントで指摘されたコメント数
* ``rejected_count`` : 差し戻し回数
* ``monitored_worktime_hour/task_count`` : タスクあたり計測作業時間
* ``monitored_worktime_hour/input_data_count`` : 入力データあたり計測作業時間
* ``monitored_worktime_hour/annotation_count`` : アノテーションあたり計測作業時間
* ``actual_worktime_hour/task_count`` : タスクあたり実績作業時間
* ``actual_worktime_hour/input_data_count`` : 入力データあたり実績作業時間
* ``actual_worktime_hour/annotation_count`` : アノテーションあたり実績作業時間
* ``pointed_out_inspection_comment_count/input_data_count`` : 入力データあたりの指摘コメント数
* ``pointed_out_inspection_comment_count/annotation_count`` : アノテーションあたりの指摘コメント数
* ``rejected_count/task_count`` : タスクあたり差し戻し回数

``first_working_date`` や ``lastweek_start_date`` などの期間に関する列は出力されません。
