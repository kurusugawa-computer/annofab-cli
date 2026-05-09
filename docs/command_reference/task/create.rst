=================================
task create
=================================

Description
=================================
タスクを作成します。

Examples
=================================


CSVファイルを指定する場合
--------------------------------------
タスクに含まれる入力データを記載したCSVを指定して、タスクを作成することができます。

CSVのフォーマットは以下の通りです。

* カンマ区切り
* ヘッダ行あり
* 必須列: ``task_id``, ``input_data_id``


以下はCSVのサンプルです。

.. code-block::
    :caption: task.csv

    task_id,input_data_id
    task_1,input_data_1
    task_1,input_data_2
    task_2,input_data_3
    task_2,input_data_4



.. code-block::

    $ annofabcli task create --project_id prj1 --csv task.csv



JSON文字列を指定する場合
--------------------------------------
タスクと入力データの関係を表したJSONを指定して、タスクを作成することができます。
JSONのフォーマットは ``task list --format json`` の出力と同じです。
ただし、 ``task create`` が参照するキーは ``task_id`` , ``input_data_id_list`` , ``metadata`` , ``user_id`` のみです。その他のキーは無視されます。

以下は、JSONのサンプルです。

.. code-block::
    :caption: task.json


    [
        {
            "task_id": "task1",
            "input_data_id_list": ["input1", "input2"],
            "metadata": {
                "priority": 1,
                "category": "foo"
            },
            "user_id": "alice"
        },
        {
            "task_id": "task2",
            "input_data_id_list": ["input3", "input4"],
            "metadata": {
                "priority": 2,
                "category": "bar"
            },
            "user_id": "bob"
        }
    ]

``user_id`` を指定すると、タスクの作成直後に担当者が割り当てられます。


.. code-block::

    $ annofabcli task create --project_id prj1 \
     --json '[{"task_id":"task1","input_data_id_list":["input1","input2"],"metadata":{"priority":1}}]'


全タスクに共通のメタデータを付与する
--------------------------------------

``--metadata`` を指定すると、作成するすべてのタスクに共通のメタデータを付与できます。

.. code-block::

    $ annofabcli task create --project_id prj1 --csv task.csv \
     --metadata '{"category":"foo","required":true}'


``--json`` の各タスクに ``metadata`` を指定した場合、 ``--metadata`` と各タスクの ``metadata`` がマージされます。
同じキーが存在するときは、各タスクの ``metadata`` が優先されます。


全タスクに共通の担当者を割り当てる
--------------------------------------

``--user_id`` を指定すると、作成するすべてのタスクに共通の担当者を割り当てることができます。

.. code-block::

    $ annofabcli task create --project_id prj1 --csv task.csv \
     --user_id alice


``--json`` の各タスクに ``user_id`` を指定した場合、 ``--user_id`` より各タスクの ``user_id`` が優先されます。



Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.create_tasks.add_parser
   :prog: annofabcli task create
   :nosubcommands:
   :nodefaultconst:
