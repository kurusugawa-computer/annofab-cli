==========================================
task_history_event download
==========================================

Description
=================================
タスク履歴イベント全件ファイルをダウンロードします。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドを実行すると、タスク履歴イベント全件ファイルがダウンロードされます。
タスク履歴イベント全件ファイルのフォーマットについては https://annofab.com/docs/api/#section/TaskHistoryEvent を参照してください。

.. code-block::

    $ annofabcli task_history_event download --project_id prj1 --output task_history_event.json

タスク履歴イベントの状態は、02:00(JST)頃にタスク履歴イベント全件ファイルに反映されます。



Usage Details
=================================

.. argparse::
    :ref: annofabcli.task_history_event.download_task_history_event_json.add_parser
    :prog: annofabcli task_history_event download
    :nosubcommands:
    :nodefaultconst:


