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

実行すると、作成前に確認メッセージが表示されます。確認を省略したい場合は ``--yes`` を指定してください。


JSON文字列を指定する場合
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
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

各要素の ``task_id`` にtask_idを指定して、 ``input_data_id_list`` にinput_data_idの配列を指定してください。
メタデータを付与する場合は、 ``metadata`` にオブジェクトを指定してください。
メタデータの値には文字列、数値、真偽値を指定できます。
タスクの担当者を指定する場合は、 ``user_id`` にプロジェクトメンバーのuser_idを指定してください。

JSON形式の文字列、またはJSONファイルのパスは ``--json`` に渡します。

.. code-block::

    $ annofabcli task create --project_id prj1 \
     --json '[{"task_id":"task1","input_data_id_list":["input1","input2"],"metadata":{"priority":1}}]'


全タスクに共通のメタデータを付与する
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``--metadata`` を指定すると、作成するすべてのタスクに共通のメタデータを付与できます。
CSVファイルでタスクを作成するときにも利用できます。

.. code-block::

    $ annofabcli task create --project_id prj1 --csv task.csv \
     --metadata '{"category":"foo","required":true}'


``--json`` の各タスクに ``metadata`` を指定した場合、 ``--metadata`` と各タスクの ``metadata`` がマージされます。
同じキーが存在するときは、各タスクの ``metadata`` が優先されます。

.. code-block::

    $ annofabcli task create --project_id prj1 \
     --json '[{"task_id":"task1","input_data_id_list":["input1"],"metadata":{"priority":1}}]' \
     --metadata '{"category":"foo","priority":999}'

上記の場合、 ``task1`` には以下のメタデータが設定されます。

.. code-block:: json

    {
        "category": "foo",
        "priority": 1
    }


全タスクに共通の担当者を割り当てる
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``--user_id`` を指定すると、作成するすべてのタスクに共通の担当者を割り当てることができます。
CSVファイルでタスクを作成するときにも利用できます。

.. code-block::

    $ annofabcli task create --project_id prj1 --csv task.csv \
     --user_id alice


``--json`` の各タスクに ``user_id`` を指定した場合、 ``--user_id`` より各タスクの ``user_id`` が優先されます。

.. code-block::

    $ annofabcli task create --project_id prj1 \
     --json '[{"task_id":"task1","input_data_id_list":["input1"],"user_id":"bob"}]' \
     --user_id alice

上記の場合、 ``task1`` の担当者には ``bob`` が設定されます。


並列でタスクを作成する
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

``--parallelism`` を指定すると、複数のタスクを並列で作成できます。
``--parallelism`` を指定する場合は、確認メッセージを省略するために ``--yes`` も指定してください。

.. code-block::

    $ annofabcli task create --project_id prj1 --csv task.csv \
     --parallelism 4 --yes


Usage Details
=================================

.. argparse::
   :ref: annofabcli.task.create_tasks.add_parser
   :prog: annofabcli task create
   :nosubcommands:
   :nodefaultconst:
