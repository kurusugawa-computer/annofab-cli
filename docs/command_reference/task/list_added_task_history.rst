==========================================
task list_added_task_history
==========================================

Description
=================================
タスク一覧に、タスク履歴に関する情報に加えたものを出力します。
タスク履歴に関する情報は、たとえば以下のような情報です。

* フェーズごとの作業時間
* 各フェーズの最初の担当者と開始日時



Examples
=================================


基本的な使い方
--------------------------

.. code-block::

    $ annofabcli task list_added_task_history --project_id prj1 --output task.csv


.. warning::

    WebAPIの都合上、タスクは10,000件までしか出力できません。
    10,000件以上のタスクを出力する場合は、`annofabcli task list_all_added_task_history <../task/list_all_added_task_history.html>`_ コマンドを使用してください。



タスクのフェーズやステータスなどで絞り込む
----------------------------------------------
``--task_query`` を指定すると、タスクのフェーズやステータスなどで絞り込めます。

``--task_query`` に渡す値は、https://annofab.com/docs/api/#operation/getTasks のクエリパラメータとほとんど同じです。
さらに追加で、``user_id`` , ``previous_user_id`` キーも指定できます。

以下のコマンドは、受入フェーズで完了状態のタスク一覧を出力します。


.. code-block::

    $ annofabcli task list_added_task_history --project_id prj1 \
     --task_query '{"status":"complete", "phase":"not_started"}'



task_id絞り込む
--------------------------------------------------------------------------------------------
``--task_id`` を指定すると、タスクIDで絞り込むことができます。

.. code-block::

    $ annofabcli task list_added_task_history --project_id prj1 \
     --task_id task1 task2



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
        "first_acceptance_reached_datetime": "2022-10-24T15:14:18.967+09:00",
        "first_acceptance_completed_datetime": "2022-10-25T15:14:18.967+09:00",
        "completed_datetime": "2022-10-25T15:14:18.967+09:00",
        "inspection_is_skipped": false,
        "acceptance_is_skipped": false,
        "post_rejection_annotation_worktime_hour": 0.0,
        "post_rejection_inspection_worktime_hour": 0.0,
        "post_rejection_acceptance_worktime_hour": 0.0
        
    },
    ...
    ]

以下の項目は、タスク履歴から算出した情報です。


日時
^^^^^^^^^^^^^^^^^^^^^^^

* ``created_datetime`` : タスクの作成日時
* ``first_annotation_started_datetime`` : 初めて教師付フェーズを着手した日時
* ``first_inspection_started_datetime`` : 初めて検査フェーズを着手した日時
* ``first_acceptance_started_datetime`` : 初めて受入フェーズを着手した日時
* ``first_acceptance_reached_datetime`` : 初めて受入フェーズに到達した日時。 ``first_acceptance_started_datetime`` より前の日時になる
* ``first_acceptance_completed_datetime`` : 初めて受入フェーズかつ完了状態になった日時
* ``completed_datetime`` : 受入フェーズかつ完了状態になった日時



作業時間
^^^^^^^^^^^^^^^^^^^^^^^

* ``annotation_worktime_hour`` : 教師付フェーズの作業時間
* ``inspection_worktime_hour`` : 検査フェーズの作業時間
* ``acceptance_worktime_hour`` : 受入フェーズの作業時間
* ``first_annotation_worktime_hour`` : 最初の教師付フェーズの作業時間
* ``first_inspection_worktime_hour`` : 最初の検査フェーズの作業時間
* ``first_acceptance_worktime_hour`` : 最初の受入フェーズの作業時間
* ``post_rejection_annotation_worktime_hour`` : 検査/受入フェーズでの差し戻し以降の教師付フェーズの作業時間[hour]
* ``post_rejection_inspection_worktime_hour`` : 検査/受入フェーズでの差し戻し以降の検査フェーズの作業時間[hour]
* ``post_rejection_acceptance_worktime_hour`` : 受入フェーズでの差し戻し以降の検査フェーズの作業時間[hour]



ユーザー情報
^^^^^^^^^^^^^^^^^^^^^^^

* ``first_annotation_user_id`` : 最初の教師付フェーズを担当したユーザのuser_id
* ``first_annotation_username`` : 最初の教師付フェーズを担当したユーザの名前
* ``first_inspection_user_id`` : 最初の検査フェーズを担当したユーザのuser_id
* ``first_inspection_username`` : 最初の検査フェーズを担当したユーザの名前
* ``first_acceptance_user_id`` : 最初の受入フェーズを担当したユーザのuser_id
* ``first_acceptance_username`` : 最初の受入フェーズを担当したユーザの名前


その他
^^^^^^^^^^^^^^^^^^^^^^^

* ``inspection_is_skipped`` : 抜取検査により検査フェーズがスキップされたかどうか
* ``acceptance_is_skipped`` : 抜取受入により受入フェーズがスキップされたかどうか






Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.list_tasks_added_task_history.add_parser
   :prog: annofabcli task list_added_task_history
   :nosubcommands:
   :nodefaultconst:
