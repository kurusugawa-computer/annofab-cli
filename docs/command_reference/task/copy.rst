=================================
task copy
=================================

Description
=================================
タスクをコピーします。


Examples
=================================


基本的な使い方
--------------------------

``--task_id`` にコピー元タスクのtask_id、 ``--dest_task_id`` にコピー先タスクのtask_idを指定してください。
``--task_id`` に渡すタスクの個数と ``--dest_task_id`` に渡すタスクの個数は合わせる必要があります。

.. code-block::

    $ annofabcli task copy --project_id prj1 --task_id t1 t2 \
    --dest_task_id t3 t4

``--copy_metadata`` を指定すれば、タスクのメタデータもコピーされます。


.. code-block::

    $ annofabcli task copy --project_id prj1 --task_id t1 t2 \
    --dest_task_id t3 t4 --copy_metadata

