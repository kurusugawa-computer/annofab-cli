==========================================
task_history download
==========================================

Description
=================================
タスク履歴全件ファイルをダウンロードします。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドを実行すると、タスク履歴全件ファイルがダウンロードされます。
タスク履歴全件ファイルのフォーマットについては https://annofab.com/docs/api/#section/TaskHistory を参照してください。

.. code-block::

    $ annofabcli task_history download --project_id prj1 --output task_history.json

タスク履歴の状態は、02:00(JST)頃にタスク履歴全件ファイルに反映されます。



Usage Details
=================================

.. argparse::
    :ref: annofabcli.task_history.download_task_history_json.add_parser
    :prog: annofabcli task_history download
    :nosubcommands:
    :nodefaultconst:


