=================================
task update_metadata
=================================

Description
=================================
タスクのメタデータを更新します。


Examples
=================================




タスクのメタデータを更新します。





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




デフォルトでは ``--metadata`` に指定したキーのみ更新されます。メタデータ自体を上書きする場合は ``--overwrite`` を指定してください。


.. code-block::

    $ annofabcli task update_metadata --project_id prj1 --task_id task1 \
     --metadata '{"category":"202010"}'

    $ annofabcli task list --project_id prj1 --task_id task1 \
     --format json --query "[0].metadata"
    {"category": "202010"}

    # メタデータの一部のキーのみ更新する
    $ annofabcli task update_metadata --project_id prj1 --task_id task1 \
     --metadata '{"country":"Japan"}'
    $ annofabcli task list --project_id prj1 --task_id task1 \
     --format json --query "[0].metadata"
    {"category": "202010", "country":"Japan"}

    # メタデータ自体を上書きする
    $ annofabcli task update_metadata --project_id prj1 --task_id task1 \
     --metadata '{"weather":"sunny"}' --overwrite
    $ annofabcli task list --project_id prj1 --task_id task1 \
     --format json --query "[0].metadata"
    {"weather":"sunny"}




.. note::

    ``--overwrite --yes`` の両方を指定すると、通常より処理時間が大幅に短くなります。これは、task_idを複数指定できる `patchTasksMetadata <https://annofab.com/docs/api/#operation/patchTasksMetadata>`_ WebAPIを使ってタスクのメタデータを更新するからです。
    1万件以上の大量のタスクに対して初めてメタデータを付与するときは、``--overwrite --yes`` オプションを指定することを推奨します。




並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $ annofabcli task update_metadata --project_id prj1 \
     --task_id file://input_data_id.txt \
     --metadata '{"category":"202010"}' --parallelism 4 --yes





Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.update_metadata_of_task.add_parser
   :prog: annofabcli task update_metadata
   :nosubcommands:
   :nodefaultconst:
