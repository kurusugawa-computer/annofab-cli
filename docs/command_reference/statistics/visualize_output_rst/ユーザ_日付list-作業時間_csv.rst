==========================================
ユーザ_日付list-作業時間.csv
==========================================

ユーザごと日毎の作業時間が記載されています。


`ユーザ_日付list-作業時間.csvのサンプル <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/statistics/visualize/out_dir/ユーザ_日付list-作業時間.csv>`_



列の内容
===================================================================================================

単位は「時間」です。

* ``actual_worktime_hour`` : 実績作業時間（ ``--labor_csv`` で渡された実際の作業時間）。
* ``monitored_worktime_hour`` : 計測作業時間（アノテーションエディタ画面を触っていた作業の時間）。
* ``monitored_annotation_worktime_hour`` ：教師付フェーズの計測作業時間
* ``monitored_inspection_worktime_hour`` ：検査フェーズの計測作業時間
* ``monitored_acceptance_worktime_hour`` ：受入フェーズの計測作業時間

