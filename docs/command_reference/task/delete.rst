=================================
task delete
=================================

Description
=================================
タスクを削除します。

ただしタスクのステータスが「作業中」または「完了」の場合は、タスクを削除できません。


Examples
=================================


基本的な使い方
--------------------------

``--task_id`` に削除対象タスクのtask_idを指定してください。

.. code-block::
    :caption: task_id.txt

    task1
    task2
    ...


.. code-block::

    $ annofabcli task delete --project_id prj1 --task_id file://task_id.txt


デフォルトでは、アノテーションが付与されているタスクは削除できません。
アノテーションが付与されているタスクを削除する場合は ``--force`` を指定してください。

.. code-block::

    $ annofabcli task delete --project_id prj1 --task_id file://task_id.txt --force


``--delete_input_data`` を指定すれば、タスクが参照している入力データとそれに紐づく補助情報も削除されます。ただし、他のタスクから参照されている入力データは、削除されません。


.. code-block::

    $ annofabcli task delete --project_id prj1 --task_id file://task_id.txt --delete_input_data




タスクのフェーズやステータスなどで絞り込み
----------------------------------------------
``--task_query`` を指定すると、タスクのフェーズやステータスなどで、削除対象のタスクを絞り込むことができます。


以下のコマンドは ``task_id.txt`` に記載されているタスクの内、教師付フェーズで未着手のタスクを削除します。


.. code-block::

    $ annofabcli task delete --project_id prj1 --task_id file://task_id.txt \
     --task_query '{"phase":"annotation", "status:"not_started"}'

Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.delete_tasks.add_parser
   :prog: annofabcli task delete
   :nosubcommands:
   :nodefaultconst:
