==========================================
task_history list_with_json
==========================================

Description
=================================
タスク履歴全件ファイルからタスク履歴一覧を出力します。


Examples
=================================


基本的な使い方
--------------------------

以下のコマンドは、タスク履歴全件ファイルをダウンロードしてから、タスク履歴一覧を出力します。

.. code-block::

    $ annofabcli task_history list_with_json --project_id prj1


タスク履歴全件ファイルを指定する場合は、``--task_history_json`` にタスク履歴全件ファイルのパスを指定してください。
タスク全件ファイルは、`annofabcli project download <../project/download.html>`_ コマンドでダウンロードできます。


.. code-block::

    $ annofabcli task_history list_with_json --project_id prj1 --task_history.json task_history.json 


出力結果
=================================
`annofabcli task_history list <../task_history/list.html>`_ コマンドの出力結果と同じです。


.. argparse::
   :ref: annofabcli.task_history.list_task_history_with_json.add_parser
   :prog: annofabcli task_history list_with_json
   :nosubcommands:


See also
=================================
* `annofabcli project download <../project/download.html>`_
* `annofabcli task_history list <../task_history/list.html>`_
