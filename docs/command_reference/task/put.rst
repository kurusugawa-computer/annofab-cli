=================================
task put
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
* ヘッダ行なし
* 1列目: task_id
* 2列目: input_data_id


以下はCSVのサンプルです。

.. code-block::
    :caption: task.csv

    task_1,input_data_1
    task_1,input_data_2
    task_2,input_data_3
    task_2,input_data_4


``--csv`` に、CSVファイルのパスを指定してください。


.. code-block::

    $ annofabcli task put --project_id prj1 --csv task.csv


JSON文字列を指定する場合
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
タスクと入力データの関係を表したJSONを指定して、タスクを作成することができます。

以下は、JSONのサンプルです。

.. code-block::
    :caption: task.json


    {
        "task1": ["input1","input2"],
        "task2": ["input3","input4"],
    }

キーにtask_idを指定して、値にinput_data_idの配列を指定してください。

JSON形式の文字列、またはJSONファイルのパスは ``--json`` に渡します。

.. code-block::

    $ annofabcli task put --project_id prj1 --json '{"task1":["input1","input2"]}'


タスクを生成するWebAPIを指定する
--------------------------------------
タスクを生成するWebAPIは2つあります。

* ``put_task`` ： タスクを1個ずつ作成します。
* ``initiate_tasks_generation`` ： タスクを一括で生成します。タスク作成ジョブが登録され、ジョブが終了するまで数分待ちます。1個のタスク生成に失敗した場合、すべてのタスクは生成されません。

使用するWebAPIは ``--api`` で指定できます。
デフォルトでは、作成するタスク数が少ないときは ``put_task`` WebAPI、 タスク数が多いときは ``initiate_tasks_generation`` WebAPIが実行されます。

``initiate_tasks_generation`` WebAPIでは、1個のタスク生成に失敗した場合、すべてのタスクは生成されません。
タスク生成に失敗に関わらず、できるだけ多くのタスクを生成したい場合は、 ``--api put_task`` を指定することを推奨します。



タスクの作成が完了するまで待つ
--------------------------------------
タスク作成の処理は、数分かかかります。
タスクの作成が完了するまで待つ場合は、``--wait`` を指定してください。

.. code-block::

    $ annofabcli task put --project_id prj1 --csv task.csv --wait



Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.put_tasks.add_parser
   :prog: annofabcli task put
   :nosubcommands:
   :nodefaultconst:
