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


タスク全件ファイルのみ最新化する
----------------------------------------------

``--latest_task`` を指定すると、タスク全件ファイルを最新化してからダウンロードします。
このオプションは、最新のタスクのステータスやメタデータで絞り込む場合に利用できます。

ただし、タスク履歴全件ファイルは更新されません。作業時間、担当者、到達日時などのタスク履歴に関する列は最新ではなく、``completed_datetime`` のようにタスクとタスク履歴の両方を用いる列も最新性を保証しません。

.. code-block::

    $ annofabcli task list_all_added_task_history --project_id prj1 --output task.csv \
     --latest_task


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

``--add_since_date_columns`` を指定すると、指定日以降の作業時間と最初の担当者情報を、追加カラムとして出力します。
詳細は :doc:`list_added_task_history` を参照してください。

``--start_date`` （旧 ``--start_datetime`` ）は ``--add_since_date_columns`` に改名しました。既存スクリプトではオプション名を置き換えてください。

.. code-block::

    $ annofabcli task list_all_added_task_history --project_id prj1 \
     --add_since_date_columns 2026-10-01



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
