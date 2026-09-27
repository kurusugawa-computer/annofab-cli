=================================
task update_input_data
=================================

Description
=================================
既存タスクに割り当てられた入力データと、その順序を更新します。

更新後の入力データをすべて指定してください。
現在のタスクと指定内容を比較し、入力データの追加、削除、順序変更を行います。


Examples
=================================

CSVファイルを指定する
--------------------------------------

CSVの行順が、更新後のタスク内の入力データの順序になります。

.. code-block::
    :caption: task.csv

    task_id,input_data_id
    task1,input3
    task1,input1
    task1,input2
    task1,input4


.. code-block:: console

    $ annofabcli task update_input_data --project_id prj1 --csv task.csv


JSONを指定する
--------------------------------------

``input_data_id_list`` の順序が、更新後のタスク内の入力データの順序になります。
``task list --format json`` の出力も指定できますが、参照するキーは ``task_id`` と ``input_data_id_list`` だけです。

.. code-block:: json
    :caption: task.json

    [
        {
            "task_id": "task1",
            "input_data_id_list": ["input3", "input1", "input2", "input4"]
        }
    ]


.. code-block:: console

    $ annofabcli task update_input_data --project_id prj1 --json file://task.json


タスクに入力データを追加する
--------------------------------------

更新前のすべての入力データを残したまま、新しい入力データを追加できます。
既存の入力データに紐づくアノテーションは維持されます。

.. code-block:: text

    更新前: [input1, input2]
    更新後: [input1, input2, input3]


タスク内の入力データの順序を変更する
--------------------------------------

同じ入力データを更新後の順序で指定します。

.. code-block:: text

    更新前: [input1, input2, input3]
    更新後: [input3, input1, input2]


タスクから入力データを削除する
--------------------------------------

デフォルトでは、現在のタスクに含まれる入力データが更新後の指定に含まれていない場合、更新をスキップします。
入力データを削除するには ``--allow_removing_input_data`` を指定してください。

.. warning::

    タスクから入力データを削除すると、その入力データに紐づくアノテーションが削除される可能性があります。


.. code-block:: console

    $ annofabcli task update_input_data --project_id prj1 --csv task.csv \
        --allow_removing_input_data


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.update_input_data.add_parser
   :prog: annofabcli task update_input_data
   :nosubcommands:
   :nodefaultconst:
