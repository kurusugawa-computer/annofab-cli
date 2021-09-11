=================================
task update_metadata
=================================

Description
=================================
タスクのメタデータを更新します。


Examples
=================================




タスクのメタデータを更新します。
メタデータは常に上書きされることに注意してくだださい。





基本的な使い方
--------------------------------------

``--task_id`` にメタデータを付与するタスクのtask_idを指定してください。

.. code-block::
    :caption: task_id.txt

    task1
    task2
    ...


``--metadata`` にタスクに設定するメタデータをJSON形式で指定してください。
メタデータの値には文字列、数値、真偽値のいずれかを指定できます。


.. code-block::

    $ annofabcli task update_metadata --project_id prj1 --task_id file://task_id.txt \
     --metadata '{"priority":2, "rquired":true, "category":"202010"}'



.. note::

    一度に大量のタスクのメタデータを更新すると、タイムアウトが発生する場合があります。
    タイムアウトが発生した場合は、``--batch_size`` を指定して、更新するタスク数を減らしてください。


.. warning::

    メタデータを更新すると、メタデータ自体が上書きされます。
    メタデータの一部のキーのみ更新することはできません。

    .. code-block::

        $ annofabcli task list --project_id prj1 --task_id task1 --format json \
        --query "[0].metadata"
        {"priority": 2}

        # メタデータに`required`キーも追加しようとする
        $ annofabcli task update_metadata --project_id prj1 --task_id task1 \
        --metadata '{"rquired":true}'

        # 更新前の`priority`キーが消えてしまった
        $ annofabcli task list --project_id prj1 --task_id task1 --format json \
        --query "[0].metadata"
        {"required": true}


.. argparse::
   :ref: annofabcli.task.update_metadata_of_task.add_parser
   :prog: annofabcli task update_metadata
   :nosubcommands:
