==========================================
task list_all_added_task_history
==========================================

Description
=================================
`annofabcli task list <../task/list.html>`_ コマンドで取得できるタスク一覧に、タスク履歴から取得した以下の情報を追加した上で出力します。

* フェーズごとの作業時間
* 各フェーズの最初の担当者と開始日時
* 各フェーズの最後の担当者と開始日時

最初に教師付けを開始した日時や担当者などを調べるのに利用できます。


Examples
=================================


基本的な使い方
--------------------------

以下のコマンドは、タスク全件ファイルとタスク履歴全件ファイルをダウンロードしてから、タスク一覧を出力します。

.. code-block::

    $ annofabcli task list_all_added_task_history --project_id prj1 --output task.csv


タスク全件ファイルを指定する場合は ``--task_json`` 、タスク履歴全件ファイルを指定する場合は ``--task_history_json`` を指定してください。

.. code-block::

    $ annofabcli task list_all_added_task_history --project_id prj1 --output task.csv \
    --task_json task.json --task_history_json task_history.json

タスク全件ファイルは `annofabcli task download <../task/download.html>`_ コマンド、タスク履歴全件ファイルは、`annofabcli task_history download <../task_history/download.html>`_ コマンドでダウンロードできます。


タスクの絞り込み
----------------------------------------------

``--task_query`` 、 ``--task_id`` で、タスクを絞り込むことができます。


.. code-block::

    $ annofabcli task list_all_added_task_history --project_id prj1 \
     --task_query '{"status":"complete", "phase":"not_started"}'

    $ annofabcli task list_all_added_task_history --project_id prj1 \
     --task_id file://task_id.txt





出力結果
=================================




JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli task list_added_task_history --project_id prj1 --format pretty_json --output out.json


.. code-block::
    :caption: out.json

    [
    {
        "project_id": "prj1",
        "task_id": "task1",
        "phase": "acceptance",
        "phase_stage": 1,
        "status": "complete",
        "input_data_id_list": [
            "input1",
            ...
        ],
        "account_id": "12bc2dca-d519-419b-8da1-cd431d91e193",
        "histories_by_phase": [
            ...
        ],
        "work_time_span": 3110962,
        "started_datetime": "2022-10-25T15:04:24.212+09:00",
        "updated_datetime": "2022-10-25T15:14:18.986+09:00",
        "operation_updated_datetime": "2022-10-25T15:14:18.986+09:00",
        "sampling": null,
        "metadata": {
        "input_data_count": 20
        },
        "user_id": "alice",
        "username": "Alice",
        "worktime_hour": 0.8641561111111111,
        "number_of_rejections_by_inspection": 1,
        "number_of_rejections_by_acceptance": 0,
        "input_data_count": 20,
        "created_datetime": "2022-10-22T00:18:20.922+09:00",
        "first_annotation_started_datetime": "2022-10-22T13:08:26.576+09:00",
        "first_annotation_worktime_hour": 0.5416294444444444,
        "first_annotation_user_id": "bob",
        "first_annotation_username": "Bob",
        "annotation_worktime_hour": 0.5879452777777777,
        "first_inspection_started_datetime": "2022-10-25T09:44:00.589+09:00",
        "first_inspection_worktime_hour": 0.08355916666666666,
        "first_inspection_user_id": "chris",
        "first_inspection_username": "Chris",
        "inspection_worktime_hour": 0.1110011111111111,
        "first_acceptance_started_datetime": "2022-10-25T15:04:24.212+09:00",
        "first_acceptance_worktime_hour": 0.16520972222222222,
        "first_acceptance_user_id": "alice",
        "first_acceptance_username": "Alice",
        "acceptance_worktime_hour": 0.16520972222222222,
        "first_acceptance_completed_datetime": "2022-10-25T15:14:18.967+09:00",
        "completed_datetime": "2022-10-25T15:14:18.967+09:00",
        "inspection_is_skipped": false,
        "acceptance_is_skipped": false
    },
    ...
    ]



以下の項目は、タスク履歴から取得した情報です。

* created_datetime: タスクの作成日時
* annotation_worktime_hour: 教師付フェーズの作業時間[hour]
* inspection_worktime_hour: 検査フェーズの作業時間[hour]
* acceptance_worktime_hour: 受入フェーズの作業時間[hour]
* first_acceptance_completed_datetime: はじめて受入完了状態になった日時
* completed_datetime: 受入完了状態になった日時
* inspection_is_skipped: 抜取検査により検査フェーズがスキップされたかどうか
* acceptance_is_skipped: 抜取受入により受入フェーズがスキップされたかどうか
* first_annotation_user_id: 最初の教師付フェーズを担当したユーザのuser_id
* first_annotation_username: 最初の教師付フェーズを担当したユーザの名前
* first_annotation_started_datetime: 最初の教師付フェーズを開始した日時
* ...
* last_acceptance_user_id: 最後の受入フェーズを担当したユーザのuser_id
* last_acceptance_username: 最後の受入フェーズを担当したユーザの名前
* last_acceptance_started_datetime: 最後の受入フェーズを開始した日時





Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.list_all_tasks_added_task_history.add_parser
   :prog: annofabcli task list_all_added_task_history
   :nosubcommands:
   :nodefaultconst:
