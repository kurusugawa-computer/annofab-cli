=================================
task delete_metadata_key
=================================

Description
=================================
タスクのメタデータのキーを削除します。


Examples
=================================


``--metadata_key`` に削除したいメタデータのキーを指定します。


.. code-block::

    $ annofabcli task delete_metadata_key --project_id prj1 --task_id task1 task2 \
     --metadata_key foo bar



.. warning::

    タスクのメタデータを更新すると、タスクの ``updated_datetime`` （更新日時）が更新されます。
    タスクの ``updated_datetime`` は、アノテーション作業以外でも更新されることに注意してください。
    



Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.delete_metadata_key_of_task.add_parser
   :prog: annofabcli task delete_metadata_key
   :nosubcommands:
   :nodefaultconst:
