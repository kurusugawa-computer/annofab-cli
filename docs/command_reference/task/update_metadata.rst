=================================
task update_metadata
=================================

Description
=================================
タスクのメタデータを更新します。


Examples
=================================



基本的な使い方
--------------------------------------



``--metadata`` にタスクに設定するメタデータをJSON形式で指定します。
メタデータの値には文字列、数値、真偽値を指定できます。


.. code-block::

    $ annofabcli task update_metadata --project_id prj1 --task_id task1 task2 \
     --metadata '{"priority":2, "required":true, "category":"202010"}'




デフォルトでは ``--metadata`` に指定したキーのみ更新されます。メタデータ自体を上書きする場合は ``--overwrite`` を指定してください。



.. note::

    タスクのメタデータは ``task list`` コマンドで確認できます。
    ``task list`` の出力結果は情報量が多いので、以下のようにjqコマンドを使って情報を絞り込むと、見やすくなります。
    
    .. code-block::
        
        $ annofabcli task list --project_id prj1 --task_id task1 --format json |
            jq '[.[] | {task_id,metadata}]'
        [
            {
                "task_id": "task1",
                "metadata": {
                    "category": "202010",
                    "priority": 2,
                    "required": true
                }
            }
        ]  

    



.. code-block::

    $ annofabcli task update_metadata --project_id prj1 --task_id task1 \
     --metadata '{"category":"202010"}'

    $ annofabcli task list --project_id prj1 --task_id task1 --format json | \
    jq '[.[] | {task_id,metadata}]'
    [
        {
            "task_id": "task1",
            "metadata": {
                "category": "202010"
            }
        }
    ]
    
    # メタデータの一部のキーのみ更新する
    $ annofabcli task update_metadata --project_id prj1 --task_id task1 \
     --metadata '{"country":"Japan"}'
    
    $ annofabcli task list --project_id prj1 --task_id task1 --format json | \
    jq '[.[] | {task_id,metadata}]'
    [ 
        {
            "task_id": "task1",
            "metadata": {
                "category": "202010",
                "country":"Japan"
            }
        }
     ]

    # メタデータ自体を上書きする
    $ annofabcli task update_metadata --project_id prj1 --task_id task1 \
     --metadata '{"weather":"sunny"}' --overwrite
     
    $ annofabcli task list --project_id prj1 --task_id task1 --format json | \
    jq '[.[] | {task_id,metadata}]'
    [
    {
        "task_id": "task1",
        "metadata": {
            "weather": "sunny"
        }
    }
    ]




.. note::

    ``--overwrite --yes`` の両方を指定すると、通常より処理時間が大幅に短くなります。これは、task_idを複数指定できる `patchTasksMetadata <https://annofab.com/docs/api/#operation/patchTasksMetadata>`_ WebAPIを使ってタスクのメタデータを更新するからです。
    1万件以上の大量のタスクに対して初めてメタデータを付与するときは、``--overwrite --yes`` オプションを指定することを推奨します。




.. warning::

    タスクのメタデータを更新すると、タスクの ``updated_datetime`` （更新日時）が更新されます。
    タスクの ``updated_datetime`` は、アノテーション作業以外でも更新されることに注意してください。
    



タスクごとにメタデータを指定する
--------------------------------------

``--metadata_by_task_id`` を指定すれば、タスクごとにメタデータを指定できます。


.. code-block:: json
    :caption: all_metadata.json
    
    {
      "task1": {"priority":1},
      "task2": {"priority":2}
    }
    
    
.. code-block::

    $ annofabcli task update_metadata --project_id prj1 \
     --metadata_by_task_id file://all_metadata.json


``--metadata_by_task_id`` に指定するJSONのフォーマットは、以下のjqコマンドで生成できます。
プロジェクト ``prj1`` と ``prj2`` で同じタスクを管理している状況で、プロジェクト ``prj1`` のタスクのメタデータをプロジェクト ``prj2`` にコピーするときに便利です。





.. code-block::

    $ annofabcli task list --project_id prj1 --format json | \
     jq  'map({(.task_id):.metadata}) | add' > tmp.json
    
    $ cat tmp.json
    {
      "task1": {"priority":1},
      "task2": {"priority":2}
    }   

    $ annofabcli task update_metadata --project_id prj2 \
     --metadata_by_task_id file://tmp.json


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
