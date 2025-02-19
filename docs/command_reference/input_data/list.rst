=====================
input_data list
=====================

Description
=================================
入力データ一覧を出力します。


Examples
=================================

基本的な使い方
--------------------------

以下のコマンドは、すべての入力データの一覧を出力します。 ただし10,000件までしか出力できません。

.. code-block::

    $ annofabcli input_data list --project_id prj1


.. warning::

    WebAPIの都合上、10,000件までしか出力できません。
    10,000件以上の入力データを出力する場合は、`annofabcli input_data list_all <../input_data/list_all.html>`_ コマンドを使用してください。




絞り込み
-------------------------------------------------------

``--input_data_query`` を指定すると、入力データの名前やinput_data_idで絞り込めます。
``--input_data_query`` に渡す値は、https://annofab.com/docs/api/#operation/getInputDataList のクエリパラメータとほとんど同じです。


以下のコマンドは、入力データ名に"sample"を含む入力データの一覧を出力します。


.. code-block::

    $ annofabcli input_data list --project_id prj1 \
     --input_data_query '{"input_data_name": "sample"}' 


以下のコマンドは、task_idに"task1"を含むタスクが使用している入力データの一覧を出力します。

.. code-block::

    $ annofabcli input_data list --project_id prj1 \
     --input_data_query '{"task_id": "task1"}' 


``--input_data_id`` を指定すると、input_data_idに合致する入力データの一覧を出力します。

.. code-block::

    $ annofabcli input_data list --project_id prj1 \
     --input_data_id file://input_data_id.txt


詳細な情報を出力する
-------------------------------------------------------
以下のオプションを指定すると、より詳細な情報を出力できます。ただし、実行するWeb APIが増えるため、出力するまでの時間が長くなります。

* ``--with_parent_task_id_list`` : 入力データを参照しているタスクのtask_idのリスト
* ``--with_supplementary_data_count`` : 入力データに紐づく補助情報の個数




出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli input_data list --format csv --output out.csv

`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/input_data/list/out.csv>`_

JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli input_data list --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
        {
            "input_data_id": "input1",
            "project_id": "prj1",
            "organization_id": "org1",
            "input_data_set_id": ",12345678-abcd-1234-abcd-1234abcd5678",
            "input_data_name": "data1",
            "input_data_path": "s3://af-production-input/organizations/...",
            "updated_datetime": "2021-01-04T21:21:28.169+09:00",
            "sign_required": false,
            "metadata": {},
            "system_metadata": {
                "resized_resolution": null,
                "original_resolution": {
                    "width": 128,
                    "height": 128
                }
            },
            "_type": "Image"
        },
        ...
    ]




input_data_idの一覧を出力
----------------------------------------------

.. code-block::

    $ annofabcli input_data list --format input_data_id_list --output out.txt


.. code-block::
    :caption: out.txt

    input1
    input2
    ...

Usage Details
=================================

.. argparse::
   :ref: annofabcli.input_data.list_input_data.add_parser
   :prog: annofabcli input_data list
   :nosubcommands:
   :nodefaultconst:


See also
=================================
* `annofabcli input_data list_all <../input_data/list_all.html>`_     


