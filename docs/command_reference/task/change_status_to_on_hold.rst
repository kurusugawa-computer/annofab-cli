=================================
task change_status_to_on_hold
=================================

Description
=================================
タスクのステータスを保留中に変更します。

Examples
=================================


基本的な使い方
--------------------------

``--task_id`` に操作対象タスクのtask_idを指定してください。


.. code-block::
    :caption: task_id.txt

    task1
    task2
    ...

以下のコマンドは、タスク ``t1`` のステータスを保留中に変更します。
**ただし、操作対象のタスクのステータスは休憩中または未着手である必要があります。**

.. code-block::

    $ annofabcli task change_status_to_on_hold --project_id prj1 --task_id t1


保留コメントの付与
----------------------------------------------
``--comment`` に指定した内容が保留コメントとして付与されます。保留コメントは先頭の入力データに付与されます


.. code-block::

    $ annofabcli task change_status_to_on_hold --project_id prj1 --task_id t1 \
     --comment 画像が壊れているため作業できません




タスクのフェーズやステータスなどで絞り込み
----------------------------------------------
``--task_query`` を指定すると、タスクのフェーズやステータスなどで、操作対象のタスクを絞り込むことができます。


以下のコマンドは、``task_id.txt`` に記載されているタスクの内、受入フェーズのタスクに対してステータスを作業中から休憩中に変更します。


.. code-block::

    $ annofabcli task change_status_to_on_hold --project_id prj1 --task_id file://task_id.txt \
     --task_query '{"phase":"acceptance"}'



並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $  annofabcli task change_status_to_on_hold --project_id prj1 --task_id file://task.txt \
    --parallelism 4 --yes


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.change_status_to_on_hold.add_parser
   :prog: annofabcli task
   :nosubcommands:
   :nodefaultconst: