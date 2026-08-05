==========================================
task list_all_added_task_history
==========================================

Description
=================================
すべてのタスク一覧に、タスク履歴に関する情報に加えたものを出力します。
出力内容は `annofabcli task list_added_task_history <../task/list_added_task_history.html>`_ コマンドと同じです。

.. note::

    出力されるタスクとタスク履歴に関する列は、それぞれの全件ファイルの時点の状態です。
    タスク履歴全件ファイルは更新できないため、最新のタスク履歴情報は出力できません。
    


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


タスク全件ファイルのみ最新化する
----------------------------------------------

``--latest_task`` を指定すると、タスク全件ファイルを最新化してからダウンロードします。
このオプションは、最新のタスクのステータスやメタデータで絞り込む場合に利用できます。

ただし、タスク履歴全件ファイルは更新されません。作業時間、担当者、到達日時などのタスク履歴に関する列は最新ではなく、``completed_datetime`` のようにタスクとタスク履歴の両方を用いる列も最新性を保証しません。

.. code-block::

    $ annofabcli task list_all_added_task_history --project_id prj1 --output task.csv \
     --latest_task

``--task_history_json`` を指定して、利用するタスク履歴全件ファイルを固定することもできます。``--latest_task`` と ``--task_json`` は同時に指定できません。


タスクの絞り込み
----------------------------------------------

``--task_query`` 、 ``--task_id`` で、タスクを絞り込むことができます。


.. code-block::

    $ annofabcli task list_all_added_task_history --project_id prj1 \
     --task_query '{"status":"complete", "phase":"not_started"}'

    $ annofabcli task list_all_added_task_history --project_id prj1 \
     --task_id file://task_id.txt


指定日以降の作業時間や担当者を出力する
----------------------------------------------

``--start_datetime`` を指定すると、その日付以降の作業時間や担当者情報を各タスクに追加した形で出力できます。
詳細は :doc:`list_added_task_history` を参照してください。

.. code-block::

    $ annofabcli task list_all_added_task_history --project_id prj1 \
     --start_datetime 2026-10-01



出力結果
=================================

出力内容は `annofabcli task list_added_task_history <../task/list_added_task_history.html>`_ コマンドと同じです。


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.list_all_tasks_added_task_history.add_parser
   :prog: annofabcli task list_all_added_task_history
   :nosubcommands:
   :nodefaultconst:
