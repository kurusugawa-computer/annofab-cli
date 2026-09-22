==================================================
廃止予定の機能
==================================================

廃止予定の機能と代替手段をまとめています。
各機能の詳細は、リンク先のコマンドリファレンスを参照してください。

廃止予定日が決まっている機能
=================================

* :doc:`command_reference/comment/put_onhold`、:doc:`command_reference/comment/put_inspection`、:doc:`command_reference/comment/put_onhold_simply`、:doc:`command_reference/comment/put_inspection_simply`

  * 2027/04/01以降に廃止予定です。
  * 代わりに、それぞれ ``comment create_onhold``、``comment create_inspection``、``comment create_onhold_simply``、``comment create_inspection_simply`` を使用してください。

* :doc:`command_reference/input_data/put`、:doc:`command_reference/task/put`、:doc:`command_reference/supplementary/put`

  * 2027/01/01以降に廃止予定です。
  * 代わりに、それぞれ ``input_data create``、``task create``、``supplementary create`` を使用してください。

* :doc:`command_reference/project/put`

  * 2026/01/01以降に廃止予定です。
  * 代わりに ``project create`` を使用してください。

* :doc:`command_reference/statistics/visualize_annotation_count`、:doc:`command_reference/statistics/list_annotation_count`

  * 2027/01/01以降に廃止予定です。
  * ラベルごとの処理には ``annotation_zip`` コマンド群を使用してください。詳細は各コマンドリファレンスを参照してください。

廃止時期が未定の機能
=================================

* :doc:`command_reference/filesystem/draw_annotation`

  * 代わりに ``annotation_zip render`` を使用してください。

* :doc:`command_reference/annotation/download` の ``--download_full_annotation`` オプション

  * 将来、廃止される可能性があります。

* :doc:`command_reference/input_data/update_metadata` の ``--metadata_by_input_data_id`` オプション

  * 代わりに ``input_data update_metadata_per_input_data`` を使用してください。

* :doc:`command_reference/task/update_metadata` の ``--metadata_by_task_id`` オプション

  * 代わりに ``task update_metadata_per_task`` を使用してください。
