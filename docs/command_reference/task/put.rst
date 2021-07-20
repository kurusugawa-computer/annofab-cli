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

入力データを個別に指定する場合（CSV）
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
タスクに含まれる入力データを記載したCSVを指定して、タスクを作成することができます。

CSVのフォーマットは以下の通りです。

* カンマ区切り
* ヘッダ行なし
* 1列目: task_id
* 2列目: 空欄（どんな値でもよい）
* 3列目: input_data_id


以下はCSVのサンプルです。

.. code-block::
    :caption: task.csv

    task_1,,12345678-abcd-1234-abcd-1234abcd5678
    task_1,,22345678-abcd-1234-abcd-1234abcd5678
    task_2,,32345678-abcd-1234-abcd-1234abcd5678
    task_2,,42345678-abcd-1234-abcd-1234abcd5678


``--csv`` に、CSVファイルのパスを指定してください。


.. code-block::

    $ annofabcli task put --project_id prj1 --csv task.csv


入力データを個別に指定する場合（JSON）
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
タスクと入力データの関係を表したJSONを指定して、タスクを作成することができます。

以下は、JSONのサンプルです。

.. code-block::
    :caption: task.json


    {
        "task1": ["input1","input2"],
        "task2": ["input3","input4"],
    }

キーにtask_idを指定して、値にinput_data_idの配列を指定してください。

JSON形式の文字列、またはJSONファイルのパスは `--json`` に渡します。

.. code-block::

    $ annofabcli task put --project_id prj1 --json '{"task1":["input1","input2"]}'


入力データの個数を指定する場合
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
タスクに含まれる入力データの個数を指定して、タスクを作成することができます。

``--by_count`` に、タスクに含まれる入力データの個数などの情報を、JSON形式で指定してください。
フォーマットは、 `initiateTasksGeneration <https://annofab.com/docs/api/#operation/initiateTasksGeneration>`_  APIのリクエストボディ ``task_generate_rule`` を参照してください。

以下のコマンドは、「1タスクに含まれる入力データの個数を10、task_idのプレフィックスを"sample"」にしてタスクを作成します。

.. code-block::

    $ annofabcli task  put --project_id prj1 \
    --by_count '{"task_id_prefix":"sample","input_data_count":10}' 



タスクの作成が完了するまで待つ
--------------------------------------
タスク作成の処理は、数分かかかります。
タスクの作成が完了するまで待つ場合は、``--wait`` を指定してください。

.. code-block::

    $ annofabcli task put --project_id prj1 --csv task.csv --wait


完了確認の間隔や確認回数の上限を指定する場合は、``--wait_options`` を指定してください。

以下のコマンドは、タスク作成処理が完了したかを30秒ごとに確認し、最大10回問い合わせます（5分間待待つ）。

.. code-block::

    $ annofabcli task put --project_id prj1 --csv task.csv --wait \
    --wait_options '{"interval":30, "max_tries":10}'

