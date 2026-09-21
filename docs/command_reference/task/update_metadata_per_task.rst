=================================
task update_metadata_per_task
=================================

Description
=================================

タスクごとに指定したメタデータを更新します。


Examples
=================================

``--json`` には、 ``task list --format json`` と同じ形式のJSON配列を指定します。
各要素の ``task_id`` と ``metadata`` キーを参照し、それ以外のキーは無視します。
メタデータの値には文字列、数値、真偽値を指定できます。

.. code-block:: json
   :caption: all_metadata.json

   [
     {"task_id": "task1", "metadata": {"priority": 1}},
     {"task_id": "task2", "metadata": {"priority": 2}}
   ]

.. code-block::

   $ annofabcli task update_metadata_per_task --project_id prj1 \
     --json file://all_metadata.json

デフォルトでは、JSONに指定したキーのみ更新されます。メタデータ全体を上書きするには ``--overwrite`` を指定してください。
``--overwrite --yes`` を指定すると、通常より短時間で更新できます。詳細は :doc:`update_metadata` を参照してください。


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.update_metadata_per_task.add_parser
   :prog: annofabcli task update_metadata_per_task
   :nosubcommands:
   :nodefaultconst:
