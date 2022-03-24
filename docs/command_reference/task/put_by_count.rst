=================================
task put_by_count
=================================

Description
=================================
タスクに割り当てる入力データの個数を指定して、タスクを作成します。


Examples
=================================


基本的な使い方
--------------------------------------


以下のコマンドは、「task_idのプレフィックスが"sample"で、タスクに含まれる入力データの個数を10個」のタスクを作成します。

.. code-block::

    $ annofabcli task put --project_id prj1 \
    --task_id_prefix sample --input_data_count 10



タスクの作成が完了するまで待つ
--------------------------------------
タスク作成の処理は、数分かかかります。
タスクの作成が完了するまで待つ場合は、``--wait`` を指定してください。

.. code-block::

    $ annofabcli task put --project_id prj1 \
    --task_id_prefix sample --input_data_count 10 --wait


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.put_tasks_by_count.add_parser
   :prog: annofabcli task put_by_count
   :nosubcommands:
   :nodefaultconst:
