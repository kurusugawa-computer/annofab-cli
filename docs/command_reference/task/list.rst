=====================
task list
=====================

Description
=================================
タスク一覧を出力します。




Examples
=================================


基本的な使い方
--------------------------

``--project_id`` に対象プロジェクトのproject_idを指定してください。

以下のコマンドは、すべてのタスクの一覧を出力します。
ただし10,000件までしか出力できません。

.. code-block::

    $ annofabcli task list --project_id prj1


.. warning::

    WebAPIの都合上、10,000件までしか出力できません。
    10,000件以上のタスクを出力する場合は、`annofabcli task list_all <../task/list_all.html>`_ コマンドを使用してください。

タスクのフェーズやステータスなどで絞り込む
----------------------------------------------

``--task_query`` を指定すると、タスクのフェーズやステータスなどで絞り込めます。

``--task_query`` に渡す値は、https://annofab.com/docs/api/#operation/getTasks のクエリパラメータとほとんど同じです。
さらに追加で、``user_id`` , ``previous_user_id`` キーも指定できます。

以下のコマンドは、受入フェーズで完了状態のタスク一覧を出力します。

.. code-block::

    $ annofabcli task list --project_id prj1 \
     --task_query '{"status":"complete", "phase":"acceptance"}'


task_idに ``sample`` を含むタスクの一覧を出力します。大文字小文字は区別しません。

.. code-block::

    $ annofabcli task list --project_id prj1 \
     --task_query '{"task_id":"sample"}'


差し戻されたタスクの一覧を出力します。

.. code-block::

    $ annofabcli task list --project_id prj1 --task_query '{"rejected_only": true}'


過去の担当者が ``user1`` であるタスクの一覧を出力します。

.. code-block::

    $ annofabcli task list --project_id prj1 --task_query '{"previous_user_id": "user1"}'

metadataの ``priority`` が ``5`` であるタスク一覧を出力します。

.. code-block::

    $ annofabcli task list --project_id prj1 --task_query '{"metadata": "priority:5"}'


タスクの担当者で絞り込む
----------------------------------------------
タスクの担当者で絞り込む場合は、``--user_id`` を指定してください。

.. code-block::

    $ annofabcli task list --project_id prj1 --user_id user1 user2


task_idで絞り込む
----------------------------------------------
task_idで絞り込む場合は、 ``--task_id`` を指定してください。

.. code-block::

    $ annofabcli task list --project_id prj1 --task_id task1 task2




出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli task list --project_id prj1 --format csv --output out.csv

`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/task/list/out.csv>`_

JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli task list --project_id prj1 --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
      {
        "project_id": "prj1",
        "task_id": "task1",
        "phase": "acceptance",
        "phase_stage": 1,
        "status": "complete",
        "input_data_count": 1,
        "input_data_id_list": [
          "input1"
        ],
        "account_id": "12345678-abcd-1234-abcd-1234abcd5678",
        "histories_by_phase": [
          {
            "account_id": "12345678-abcd-1234-abcd-1234abcd5678",
            "phase": "annotation",
            "phase_stage": 1,
            "worked": true,
            "user_id": "test_user_id",
            "username": "test_username"
          },
          ...
        ],
        "started_datetime": "2020-11-24T16:21:27.753+09:00",
        "updated_datetime": "2020-11-24T16:29:29.381+09:00",
        "sampling": null,
        "metadata": {},
        "user_id": "test_user_id",
        "username": "test_username",
        "worktime_hour": 2.4789266666666667,
        "number_of_rejections_by_inspection": 0,
        "number_of_rejections_by_acceptance": 1
      },
      ...
    ]


task_idの一覧を出力
----------------------------------------------

.. code-block::

    $ annofabcli task list --project_id prj1 --format task_id_list --output out.txt


.. code-block::
    :caption: out.txt

    task1
    task2
    ...

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.list_tasks.add_parser
   :prog: annofabcli task list
   :nosubcommands:
   :nodefaultconst:

See also
=================================
* `annofabcli task list_all <../task/list_all.html>`_

