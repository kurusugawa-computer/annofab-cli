==========================================
task visualize_video_duration
==========================================

Description
=================================

タスクの動画長の分布をヒストグラムで可視化します。
タスクごとに1件として数えます。同じ入力データを2タスクが参照する場合は2件として数えます。タスク未使用の入力データは含めません。

動画長が不明なタスクは除外し、除外件数をHTMLに表示します。
対象0件の場合もHTMLを出力します。横軸は動画長、縦軸はタスク数です。

Examples
=================================

.. code-block:: bash

    $ annofabcli task visualize_video_duration --project_id prj1 --output out.html
    $ annofabcli task visualize_video_duration --project_id prj1 --task_id task1 task2 \
        --time_unit minute --bin_width 60 --output out2.html

``--task_json_file`` と ``--input_data_json_file`` を指定すると、``--project_id`` を省略できます。
1タスクに入力データが1件ある動画タスクを対象にします。それ以外はエラーになります。

``--from_date`` と ``--to_date`` は入力データの更新日で絞り込みます。
更新日時に記載されたタイムゾーンの日付で比較し、指定日当日を含みます。
``--bin_width`` は横軸の表示単位にかかわらず秒で指定します。

出力結果
=================================

:download:`出力HTMLの例 <visualize_video_duration/output/out.html>` を参照してください。
10秒の入力データを2タスクが参照し、未使用の20秒の入力データがある例です。
10秒のタスクが2件として表示され、未使用の20秒の入力データは集計対象に含まれません。

関連コマンド
=================================

一覧の取得には :doc:`list_video_duration` を使用してください。
旧コマンド :doc:`../statistics/visualize_video_duration` は非推奨です。
旧コマンドは入力データ単位で集計するため、タスク未使用の入力データも含め、共有する入力データを1回数えます。
新コマンドはタスク単位で集計するため、未使用の入力データを含めず、共有する入力データをタスクごとに数えます。
新コマンドでは不明な動画長を除外し、``--to_date`` は指定日全体を含みます。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.visualize_video_duration.add_parser
   :prog: annofabcli task visualize_video_duration
   :nosubcommands:
   :nodefaultconst:

必要なローカルファイルを指定し、``--project_id`` を省略した場合は、Annofabへの認証を行いません。
``--project_id`` を指定した場合は、プロジェクトの確認と権限チェックのため認証します。
