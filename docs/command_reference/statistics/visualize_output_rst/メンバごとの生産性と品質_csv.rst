==========================================
メンバごとの生産性と品質.csv
==========================================

メンバごとの生産量（作業したタスク数など）や生産性、教師付の品質が記載されています。

`メンバごとの生産性と品質.csvのサンプル <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/statistics/visualize/out_dir/メンバごとの生産性と品質.csv>`_


列の内容
===================================================================================================


作業時間
---------------------------------
単位は「時間」です。

* ``real_monitored_worktime_hour`` : 集計対象タスクに影響しない実際にかかった計測作業時間（アノテーションエディタ画面を触っていた作業の時間）。仕掛中のタスクにかかった作業時間も含まれます。
* ``real_actual_worktime_hour`` : 集計対象タスクに影響しない実際にかかった実績作業時間（ ``--labor_csv`` で渡された実際の作業時間）。仕掛中のタスクにかかった作業時間も含まれます。
* ``monitored_worktime_hour`` ： 集計対象タスクにかかった計測作業時間。仕掛中のタスクにかかった作業時間は含まれません。
* ``actual_worktime_hour`` ： 集計対象タスクにかかった実績作業時間。仕掛中のタスクにかかった作業時間は含まれません。 ``monitored_worktime_hour * real_monitored_worktime_hour / real_actual_worktime_hour`` で算出した値です。


集計対象タスクは、 ``--task_completion_criteria`` または ``--task_query`` （非推奨）に指定した値によって決まります。

* ``--task_completion_criteria acceptance_completed`` : 受入フェーズ完了状態のタスク
* ``--task_completion_criteria acceptance_reached`` : 受入フェーズのタスク




.. warning::

    ``--task_completion_criteria acceptance_reached`` を指定した場合、受入作業時間は0になります。
    受入フェーズに到達したタスクを「生産したタスク（作業が完了したタスク）」とする場合、受入作業時間は生産量に影響しないためです。



生産量
---------------------------------

* ``task_count`` : 集計対象タスクの数
* ``input_data_count`` : 集計対象タスクに含まている入力データの数
* ``annotation_count`` : 集計対象タスクに含まているアノテーションの数

.. note::

    複数人で同じタスクの同じフェーズを作業した場合、ユーザーごとの計測作業時間（ ``monitored_worktime_hour`` ）で按分した値を生産量として算出します。
    たとえば、task1の教師付フェーズの作業にユーザーAが45分、ユーザーBが15分かかったとします。その場合、「ユーザーAはtask1を0.75個、ユーザーBはtask1を0.25個のタスクを作業した」とみなします。
    
    上記の生産量は本来整数ですが、ユーザーごとの計測作業時間で按分しているため、小数点表記になる場合があります。



生産性の指標
---------------------------------
単位は「時間」です。

* ``monitored_worktime_hour/input_data_count`` : 入力データあたり計測作業時間
* ``actual_worktime_hour/input_data_count`` : 入力データあたり実績作業時間
* ``monitored_worktime_hour/annotation_count`` : アノテーションあたり計測作業時間
* ``actual_worktime_hour/annotation_count`` : アノテーションあたり実績作業時間

標準偏差
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
プレフィックスが ``stddev__`` である列には、標準偏差（母標準偏差）が記載されています。



品質の指標
---------------------------------
* ``pointed_out_inspection_comment_count/input_data_count`` : アノテーションあたりの指摘を受けたコメント数（対応完了状態の検査コメント）
* ``pointed_out_inspection_comment_count/annotation_count`` : アノテーションあたりの指摘を受けたコメント数（対応完了状態の検査コメント）
* ``rejected_count/task_count`` : タスクあたりの差し戻された回数


その他
---------------------------------

* ``first_working_date`` : 最初に作業した日
* ``last_working_date`` : 最後に作業した日
* ``working_days`` : 作業した日数


