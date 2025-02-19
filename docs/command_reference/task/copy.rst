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


``--input`` に、アノテーションのコピー元のtask_idとコピー先のtask_idを ``:`` で区切って指定してください。


.. code-block::

    $ annofabcli task copy --project_id prj1 \
     --input src_task_id1:dest_task_id1 src_task_id2:dest_task_id2


``--copy_metadata`` を指定すれば、タスクのメタデータもコピーされます。

.. code-block::

    $ annofabcli task copy --project_id prj1 \
     --input src_task_id1:dest_task_id1 src_task_id2:dest_task_id2 \
     --copy_metadata


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.copy_tasks.add_parser
   :prog: annofabcli task copy
   :nosubcommands:
   :nodefaultconst:
