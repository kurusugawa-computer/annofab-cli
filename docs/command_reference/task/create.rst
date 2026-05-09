=================================
task create
=================================

Description
=================================
タスクを作成します。

Examples
=================================


基本的な使い方
--------------------------------------

CSVファイルを指定する場合
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
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


``--csv`` に、CSVファイルのパスを指定してください。


.. code-block::

    $ annofabcli task create --project_id prj1 --csv task.csv


JSON文字列を指定する場合
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
タスクと入力データの関係を表したJSONを指定して、タスクを作成することができます。
JSONのフォーマットは ``task list --format json`` の出力と同じです。
ただし、 ``task create`` が参照するキーは ``task_id`` と ``input_data_id_list`` のみです。その他のキーは無視されます。

以下は、JSONのサンプルです。

.. code-block::
    :caption: task.json


    [
        {
            "task_id": "task1",
            "input_data_id_list": ["input1", "input2"]
        },
        {
            "task_id": "task2",
            "input_data_id_list": ["input3", "input4"]
        }
    ]

各要素の ``task_id`` にtask_idを指定して、 ``input_data_id_list`` にinput_data_idの配列を指定してください。

JSON形式の文字列、またはJSONファイルのパスは ``--json`` に渡します。

.. code-block::

    $ annofabcli task create --project_id prj1 --json '[{"task_id":"task1","input_data_id_list":["input1","input2"]}]'


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.create_tasks.add_parser
   :prog: annofabcli task create
   :nosubcommands:
   :nodefaultconst:
