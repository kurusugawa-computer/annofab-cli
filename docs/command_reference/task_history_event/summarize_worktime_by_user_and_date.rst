==========================================================
task_history_event summarize_worktime_by_user_and_date
==========================================================

Description
=================================

タスク履歴イベントから、ユーザーごと日付ごとの作業時間を集計します。
アノテーション・検査・受入の工程別の作業時間と、その合計を出力します。単位は時間です。
日付をまたぐ作業区間は日付ごとに分割して集計します。

作業区間ごとの明細を確認する場合は、 `annofabcli task_history_event list_worktime <list_worktime.html>`_ を参照してください。

Examples
=================================

CSV出力
---------------------------------

.. code-block:: bash

    $ annofabcli task_history_event summarize_worktime_by_user_and_date --project_id prj1 --output out.csv

.. csv-table:: out.csv
   :header-rows: 1
   :file: summarize_worktime_by_user_and_date/out.csv

JSON出力
---------------------------------

.. code-block:: bash

    $ annofabcli task_history_event summarize_worktime_by_user_and_date --project_id prj1 --format pretty_json --output out.json

.. literalinclude:: summarize_worktime_by_user_and_date/out.json
   :language: json

ダウンロード済みのタスク履歴イベントを使う場合
----------------------------------------------------------

``--task_history_event_json`` に、 `task_history_event download <download.html>`_ で取得したファイルを指定できます。
指定しない場合は、タスク履歴イベント全件ファイルをダウンロードします。
メンバー情報は、いずれの場合もAnnofabから取得します。

.. code-block:: bash

    $ annofabcli task_history_event summarize_worktime_by_user_and_date --project_id prj1 --task_history_event_json events.json --output out.csv

出力結果
=================================

* ``date``: 作業日
* ``account_id``, ``user_id``, ``username``, ``biography``: ユーザー情報
* ``worktime_hour``: 合計作業時間
* ``annotation_worktime_hour``: アノテーション作業時間
* ``inspection_worktime_hour``: 検査作業時間
* ``acceptance_worktime_hour``: 受入作業時間

作業時間が0件の場合、CSVではヘッダ行のみ、JSONでは空の配列を出力します。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task_history_event.summarize_worktime_by_user_and_date.add_parser
   :prog: annofabcli task_history_event summarize_worktime_by_user_and_date
   :nosubcommands:
   :nodefaultconst:
