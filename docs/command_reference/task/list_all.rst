=====================
task list_all
=====================

Description
=================================
すべてのタスクの一覧を出力します。

.. note::

    出力されるタスクは、コマンドを実行した日の02:00(JST)頃の状態です。
    最新の情報を出力したい場合は、 ``--latest`` を指定してください。


Examples
=================================


基本的な使い方
--------------------------

以下のコマンドは、すべてのタスクの一覧を出力します。

.. code-block::

    $ annofabcli task list_all --project_id prj1 --output task.csv


`annofabcli task download <../task/download.html>`_ コマンドでダウンロードできるタスク全件ファイルから、タスクの一覧を出力することもできます。

.. code-block::

    $ annofabcli task download --project_id prj1 --output task.json 
    $ annofabcli task list_all --project_id prj1 --task_json task.json 


タスクのフェーズやステータスなどで絞り込み
----------------------------------------------

``--task_query`` を指定すると、タスクのフェーズやステータスなどで絞り込めます。
詳細は `Command line options <../../user_guide/command_line_options.html#task-query-tq>`_ を参照してください。
以下のコマンドは、受入フェーズで未着手状態のタスクを出力します。

.. code-block::

    $ annofabcli task list_all --project_id prj1 \
     --task_query '{"status":"complete", "phase":"not_started"}'



task_idで絞り込み
----------------------------------------------
``--task_id`` を指定すると、task_idで絞り込めます。
以下のコマンドは、``task_id.txt`` に記載されているtask_idに一致するタスクを出力します。

.. code-block::

    $ annofabcli task list_all --project_id prj1 --task_id file://task_id.txt




出力結果
=================================
`annofabcli task list <../task/list.html>`_ コマンドの出力結果と同じです。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.list_all_tasks.add_parser
   :prog: annofabcli task list_all
   :nosubcommands:
   :nodefaultconst:


See also
=================================
* `annofabcli task list <../task/list.html>`_
