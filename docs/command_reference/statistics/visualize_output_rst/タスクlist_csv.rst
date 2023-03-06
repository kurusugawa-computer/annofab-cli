=====================
タスクlist.csv
=====================



タスクごとの情報が記載されています。主に以下の情報が分かります。

* 教師付/検査/受入の作業時間
* 最初に教師付/検査/受入したユーザ

以下に、列名から内容が判断しづらい列の詳細を記載します。

* number_of_rejections_by_inspection : 検査フェーズで差し戻された回数
* number_of_rejections_by_acceptance : 受入フェーズで差し戻された回数

* first_annotation_user_id : 最初に教師付フェーズを開始したユーザーのuser_id
* first_annotation_username : 最初に教師付フェーズを開始したユーザーのusername
* first_annotation_worktime_hour : 最初に教師付フェーズの作業時間[hour]
* first_annotation_started_datetime : 最初に教師付フェーズを開始した日時

* worktime_hour: 作業時間[hour]
* annotation_worktime_hour: 教師付作業時間[hour]
* inspection_worktime_hour: 検査作業時間[hour]
* acceptance_worktime_hour: 受入作業時間[hour]

* input_data_count : タスクに含まれる入力データ数
* input_data_count : タスクに含まれるアノテーション数
* inspection_comment_count : 指摘された検査コメント数（対応不要のコメントは除く）

* inspection_is_skipped : 抜取検査により検査フェーズがスキップされたか
* acceptance_is_skipped : 抜取受入により受入フェーズがスキップされたか


`タスクlist.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/statistics/visualize/out_dir/タスクlist.csv>`_
