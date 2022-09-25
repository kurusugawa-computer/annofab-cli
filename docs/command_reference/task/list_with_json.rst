=====================
task list_with_json
=====================

Description
=================================
タスク全件ファイルからタスク一覧を出力します。
10,000件以上のタスクを出力する際に利用できます。


Examples
=================================


基本的な使い方
--------------------------

以下のコマンドは、タスク全件ファイルをダウンロードしてから、タスク一覧を出力します。

.. code-block::

    $ annofabcli task list_with_json --project_id prj1 --output task.csv


タスク全件ファイルを指定する場合は、``--task_json`` にタスク全件ファイルのパスを指定してください。
タスク全件ファイルは、`annofabcli task download <../task/download.html>`_ コマンドでダウンロードできます。


.. code-block::

    $ annofabcli task list_with_json --project_id prj1 --task_json task.json \
    --output task.csv


タスクのフェーズやステータスなどで絞り込み
----------------------------------------------

``--task_query`` を指定すると、タスクのフェーズやステータスなどで絞り込めます。
以下のコマンドは、受入フェーズで未着手状態のタスクを出力します。

.. code-block::

    $ annofabcli task list_with_json --project_id prj1 \
     --task_query '{"status":"complete", "phase":"not_started"}'



task_idで絞り込み
----------------------------------------------
``--task_id`` を指定すると、task_idで絞り込めます。
以下のコマンドは、``task_id.txt`` に記載されているtask_idに一致するタスクを出力します。

.. code-block::

    $ annofabcli task list_with_json --project_id prj1 --task_id file://task_id.txt




出力結果
=================================
`annofabcli task list <../task/list.html>`_ コマンドの出力結果と同じです。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.list_tasks_with_json.add_parser
   :prog: annofabcli task list_with_json
   :nosubcommands:
   :nodefaultconst:


See also
=================================
* `annofabcli task list <../task/list.html>`_
