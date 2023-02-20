==========================================
task list_all_added_task_history
==========================================

Description
=================================
すべてのタスク一覧に、タスク履歴に関する情報に加えたものを出力します。
出力内容は `annofabcli task list_added_task_history <../task/list_added_task_history.html>`_ コマンドと同じです。

.. note::

    出力されるタスクは、コマンドを実行した日の02:00(JST)頃の状態です。
    


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

出力内容は `annofabcli task list_added_task_history <../task/list_added_task_history.html>`_ コマンドと同じです。


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.list_all_tasks_added_task_history.add_parser
   :prog: annofabcli task list_all_added_task_history
   :nosubcommands:
   :nodefaultconst:
