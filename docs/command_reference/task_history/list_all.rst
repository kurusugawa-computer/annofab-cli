==========================================
task_history list_all
==========================================

Description
=================================
すべてのタスク履歴の一覧を出力します。
出力されるタスク履歴は、コマンドを実行した日の02:00(JST)頃の状態です。最新の情報を出力したい場合は、 ``annofabcli task_history list`` コマンドを実行してください。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドは、タスク履歴全件ファイルをダウンロードしてから、タスク履歴一覧を出力します。

.. code-block::

    $ annofabcli task_history list_all --project_id prj1



`annofabcli task_history download <../task_history/download.html>`_ コマンドでダウンロードできるタスク履歴全件ファイルから、タスク履歴の一覧を出力することもできます。

.. code-block::

    $ annofabcli task_history download --project_id prj1 --output task_history.json 
    $ annofabcli task_history list_all --project_id prj1 --task_history_json task_history.json 


出力結果
=================================
`annofabcli task_history list <../task_history/list.html>`_ コマンドの出力結果と同じです。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task_history.list_all_task_history.add_parser
   :prog: annofabcli task_history list_all
   :nosubcommands:
   :nodefaultconst:


See also
=================================
* `annofabcli task_history list <../task_history/list.html>`_
