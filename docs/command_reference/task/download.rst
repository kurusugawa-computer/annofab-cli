==========================================
task download
==========================================

Description
=================================
タスク全件ファイルをダウンロードします。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドを実行すると、タスク全件ファイルがダウンロードされます。
タスク全件ファイルのフォーマットについては https://annofab.com/docs/api/#tag/x-data-types を参照してください。

.. code-block::

    $ annofabcli task download --project_id prj1 --output task.json

タスクの状態は、02:00(JST)頃にタスク全件ファイルに反映されます。
現在のタスクの状態をタスク全件ファイルに反映させたい場合は、``--latest`` を指定してください。
タスク全件ファイルへの反映が完了したら、ダウンロードされます。
ただし、データ数に応じて数分から数十分待ちます。


.. code-block::

    $ annofabcli task download --project_id prj1 --output task.json --latest


Usage Details
=================================

.. argparse::
    :ref: annofabcli.task.download_task_json.add_parser
    :prog: annofabcli task download
    :nosubcommands:
    :nodefaultconst:


