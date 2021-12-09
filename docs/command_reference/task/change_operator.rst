=================================
task change_operator
=================================

Description
=================================
タスクの担当者を変更します。
ただし作業中また完了状態のタスクは、担当者を変更できません。

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

``--user_id`` に担当させたいユーザのuser_idを指定することができます。


以下のコマンドは、タスクの担当者を ``user1`` に変更します。

.. code-block::

    $ annofabcli task change_operator --project_id prj1 --task_id file://task_id.txt \
    --user_id user1

タスクの担当者を未割当にする場合は、``--not_assign`` を指定してください。


.. code-block::

    $ annofabcli task change_operator --project_id prj1 --task_id file://task_id.txt \
    --not_assign

タスクのフェーズやステータスなどで絞り込み
----------------------------------------------
``--task_query`` を指定すると、タスクのフェーズやステータスなどで、操作対象のタスクを絞り込むことができます。


以下のコマンドは、``task_id.txt`` に記載されているタスクの内、受入フェーズで未着手のタスクに対して担当者を変更します。


.. code-block::

    $ annofabcli task change_operator --project_id prj1 --task_id file://task_id.txt \
     --task_query '{"phase":"acceptance", "status:"not_started"}' --not_assign



並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $  annofabcli task change_operator --project_id prj1 --task_id file://task.txt \
    --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.change_operator.add_parser
   :prog: annofabcli task
   :nosubcommands:
   :nodefaultconst: