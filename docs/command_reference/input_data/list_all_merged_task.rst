==========================================
input_data list_all_merged_task
==========================================

Description
=================================
すべての入力データ一覧にタスク一覧を結合した情報を出力します。

以下の情報などを知りたいときに利用できます。

* 画像プロジェクト：画像データがどのタスクで使われているか。また、フレーム番号はいくつか。
* 動画プロジェクト：タスクの動画時間の長さ


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


手元にある入力データ全件ファイル、タスク全件ファイルを指定する場合は、 ``--task_json`` , ``--input_data_json`` を指定してください。

.. code-block::

    $ annofabcli input_data list_all_merged_task --input_data_json input_data.json --task_json task.json


絞り込み
--------------------------

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

`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/input_data/list_all_merged_task/out.csv>`_


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
            "original_input_data_path": "s3://af-production-input/organizations/...",
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
                    "task_status": "break",
                    "task_phase": "acceptance",
                    "task_phase_stage": 1,
                    "frame_no": 1
                }
            ]
        },
        ...
    ]

Usage Details
=================================

.. argparse::
   :ref: annofabcli.input_data.list_all_input_data_merged_task.add_parser
   :prog: annofabcli input_data list_all_merged_task
   :nosubcommands:
   :nodefaultconst:
