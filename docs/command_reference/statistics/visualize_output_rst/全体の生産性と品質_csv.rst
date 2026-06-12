==========================================
全体の生産性と品質.csv
==========================================

全体の生産性と品質が記載されています。
:doc:`メンバごとの生産性と品質_csv` の内容を集計した値になります。


.. csv-table:: 全体の生産性と品質.csv のサンプル
    :file: ../visualize/out_dir/全体の生産性と品質.csv


列の内容
===================================================================================================

:doc:`メンバごとの生産性と品質_csv` に記載されている列に加えて、以下の列が出力されます。

* ``working_user_count`` : 作業したユーザー数
* ``lastweek_start_date`` : 直近7日間の開始日。教師付開始日が存在するタスクのうち、最大の教師付開始日から6日前の日付です。
* ``lastweek_end_date`` : 直近7日間の終了日。教師付開始日が存在するタスクのうち、最大の教師付開始日です。
* ``task_count__lastweek`` : 直近7日間に教師付開始したタスクの、タスク数
* ``input_data_count__lastweek`` : 直近7日間に教師付開始したタスクの、入力データ数
* ``annotation_count__lastweek`` : 直近7日間に教師付開始したタスクの、アノテーション数
* ``monitored_worktime_hour/task_count`` : タスクあたり計測作業時間
* ``actual_worktime_hour/task_count`` : タスクあたり実績作業時間
* ``monitored_worktime_hour/task_count__lastweek`` : 直近7日間に教師付開始したタスクの、タスクあたり計測作業時間
* ``actual_worktime_hour/task_count__lastweek`` : 直近7日間に教師付開始したタスクの、タスクあたり実績作業時間
* ``monitored_worktime_hour/input_data_count__lastweek`` : 直近7日間に教師付開始したタスクの、入力データあたり計測作業時間
* ``actual_worktime_hour/input_data_count__lastweek`` : 直近7日間に教師付開始したタスクの、入力データあたり実績作業時間
* ``monitored_worktime_hour/annotation_count__lastweek`` : 直近7日間に教師付開始したタスクの、アノテーションあたり計測作業時間
* ``actual_worktime_hour/annotation_count__lastweek`` : 直近7日間に教師付開始したタスクの、アノテーションあたり実績作業時間
