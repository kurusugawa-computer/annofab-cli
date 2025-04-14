=====================
タスクlist.csv
=====================

タスクごとの情報が記載されています。


`タスクlist.csvのサンプル <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/statistics/visualize/out_dir/タスクlist.csv>`_


列の内容
===================================================================================================



最初のフェーズに関する情報
--------------------------

* ``first_annotation_user_id`` : 最初の教師付フェーズを開始したユーザーのuser_id
* ``first_annotation_username`` : 最初の教師付フェーズを開始したユーザーの名前
* ``first_annotation_worktime_hour`` : 最初の教師付フェーズの作業時間
* ``first_annotation_started_datetime`` : 最初の教師付フェーズを開始した日時

検査フェーズ（ ``inspection`` ）と受入フェーズ（ ``acceptance`` ）に関する情報も、同様に記載されています。


日時
--------------------------

* ``created_datetime`` : タスクの作成日時
* ``first_acceptance_reached_datetime`` : 初めて受入フェーズに到達した日時
* ``first_acceptance_completed_datetime`` : 初めて受入フェーズで完了状態になった日時



作業時間
--------------------------

* ``worktime_hour`` : 作業時間
* ``annotation_worktime_hour`` : 教師付フェーズの作業時間
* ``inspection_worktime_hour`` : 検査フェーズの作業時間
* ``acceptance_worktime_hour`` : 受入フェーズの作業時間


個数
--------------------------
* ``input_data_count`` : タスクに含まれる入力データの数
* ``annotation_count`` : タスクに含まれるアノテーションの数
* ``inspection_comment_count`` : 指摘された検査コメントの数。ただし対応完了状態の検査コメントのみ。
* ``inspection_comment_count_in_inspection_phase`` : 検査フェーズで指摘された検査コメントの数
* ``inspection_comment_count_in_acceptance_phase`` : 受入フェーズで指摘された検査コメントの数


その他
--------------------------
* ``number_of_rejections_by_inspection`` : 検査フェーズで差し戻された回数
* ``number_of_rejections_by_acceptance`` : 受入フェーズで差し戻された回数
* ``inspection_is_skipped`` : 抜取検査により検査フェーズがスキップされたか
* ``acceptance_is_skipped`` : 抜取受入により受入フェーズがスキップされたか
* ``post_rejection_annotation_worktime_hour`` : 検査/受入フェーズでの差し戻し以降の教師付フェーズの作業時間[hour]
* ``post_rejection_inspection_worktime_hour`` : 検査/受入フェーズでの差し戻し以降の検査フェーズの作業時間[hour]
* ``post_rejection_acceptance_worktime_hour`` : 受入フェーズでの差し戻し以降の検査フェーズの作業時間[hour]




