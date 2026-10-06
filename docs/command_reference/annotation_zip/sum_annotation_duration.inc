集計の仕様
--------------------------

対象は動画プロジェクトの区間アノテーション（Range）です。動画以外のプロジェクトはエラーになります。
区間長は ``(end - begin) / 1000`` の合計です。重なった区間もそれぞれ加算するため、合計が動画長を超える場合があります。

``video_duration_second`` は集計対象の動画長の合計です。区間や対象ラベルがない入力データも動画長に含めます。
同じ動画が複数のタスクに含まれる場合はタスクごとに数えます。
対象はアノテーションZIPに含まれる入力データに限り、入力データ全件ファイルだけにある動画は含めません。
動画長が取得できない入力データを1件でも含む集計結果では、JSONは ``null``、CSVは空欄とし、警告を出力します。

アノテーション仕様に定義された対象ラベル・選択肢は、未出現でも0秒を出力します。
CSVの出力件数が0件の場合もヘッダーを出力します。単位は秒に固定しています。

``--project_id`` は必須です。 ``--annotation`` を指定しても、動画長・タスク情報・アノテーション仕様はAnnofabから取得します。

デフォルトはタスク単位です。入力データ単位の場合は ``--group_by input_data_id`` を指定します。

.. include:: count_group_by.inc

.. include:: task_metadata.inc

旧コマンドからの移行
--------------------------

``statistics list_annotation_duration --type label`` は ``sum_annotation_duration_by_label``、
``--type attribute`` は ``sum_annotation_duration_by_attribute_value`` に対応します。
旧コマンドと同じ入力データ単位にするには ``--group_by input_data_id`` を指定してください。
新コマンドは属性値JSONキーを ``annotation_duration_second_by_attribute_value`` に統一しています。
