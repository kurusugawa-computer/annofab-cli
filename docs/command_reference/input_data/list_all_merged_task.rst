==========================================
input_data list_all_merged_task
==========================================

Description
=================================
すべての入力データ一覧にタスク一覧を結合した情報を出力します。

入力データがどのタスクで使われているかを参照するときに有用です。


.. note::

    出力される入力データとタスクは、コマンドを実行した日の02:00(JST)頃の状態です。
    最新の情報を出力したい場合は、 ``--latest`` 引数を指定してください。



Examples
=================================

基本的な使い方
--------------------------


以下のコマンドは、入力データ全件ファイル、タスク全件ファイルをダウンロードしてから、一覧を出力します。

.. code-block::

    $ annofabcli input_data list_all_merged_task --project_id prj1 


絞り込み
--------------------------

``--input_data_name`` を指定すると、指定した名前のいずれかに部分一致する入力データを出力します。大文字小文字は区別しません。
``--input_data_id`` や ``--input_data_query`` と併用すると、すべての条件に一致する入力データを出力します。

.. code-block:: bash

    $ annofabcli input_data list_all_merged_task --project_id prj1 \
      --input_data_name sample example

``--input_data_name`` は、改行区切りの名前一覧を ``file://`` で指定することもできます。
ファイル指定は1個だけ渡してください。直接指定する値や別のファイル指定とは併用できません。

.. code-block:: text
    :caption: input_data_names.txt

    sample
    example

.. code-block:: bash

    $ annofabcli input_data list_all_merged_task --project_id prj1 \
      --input_data_name file://input_data_names.txt

``--input_data_query`` を指定すると、入力データの名前や入力データのパスで絞り込めます。


以下のコマンドは、入力データ名に"sample"を含む一覧を出力します。

.. code-block::

    $ annofabcli input_data list_all_merged_task --project_id prj1  \
     --input_data_query '{"input_data_name": "sample"}' 



``--input_data_id`` を指定すると、input_data_idに合致する入力データの一覧を出力します。

.. code-block::

    $ annofabcli input_data list_all_merged_task --project_id prj1 \
     --input_data_id file://input_data_id.txt


``--not_used_by_task`` を指定すれば、タスクに使われていない入力データがあります。「入力データは登録したがタスクは登録していなかった」などのデータ登録のミスを探すときに、 このオプションは便利です。


``--used_by_multiple_task`` を指定すれば、複数のタスクから使われている入力データが出力されます。
基本的な運用では、1個の入力データは複数のタスクから参照されることはありません。複数のタスクから参照されている場合は、データ登録のミスの可能性があります。このようなミスを探すときに、 このオプションは便利です。



出力結果
=================================







CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli input_data list_all_merged_task --project_id prj1 --format csv --output out.csv


.. csv-table:: out.csv 
    :header-rows: 1
    :file: list_all_merged_task/out.csv


JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli input_data list_all_merged_task --project_id prj1 --format pretty_json --output out.json



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
                    "width": 80,
                    "height": 80
                },
                "_type": "Image"
            },
            "parent_task_list": [
                {
                    "task_id": "test_16",
                    "task_phase": "acceptance",
                    "task_phase_stage": 1,
                    "task_status": "break",
                    "frame_no": 1
                }
            ]
        },
        ...
    ]

Usage Details
=================================

.. argparse::
   :ref: annofabcli.input_data.list_all_input_data_merged_task.create_parser
   :prog: annofabcli input_data list_all_merged_task
   :nosubcommands:
   :nodefaultconst:
