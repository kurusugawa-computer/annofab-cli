==========================================
input_data download
==========================================

Description
=================================
入力データ全件ファイルをダウンロードします。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドを実行すると、入力データ全件ファイルがダウンロードされます。
入力データ全件ファイルのフォーマットについては https://annofab.com/docs/api/#section/InputData を参照してください。

.. code-block::

    $ annofabcli input_data download --project_id prj1 --output input_data.json

入力データの状態は、02:00(JST)頃に入力データ全件ファイルに反映されます。
現在の入力データの状態を入力データ全件ファイルに反映させたい場合は、``--latest`` を指定してください。
入力データ全件ファイルへの反映が完了したら、ダウンロードされます。
ただし、データ数に応じて数分から数十分待ちます。


.. code-block::

    $ annofabcli input_data download --project_id prj1 --output input_data.json --latest



出力結果
=================================


.. code-block::

    $ annofabcli input_data download --output out.json
    $ jq . out.json > out-pretty.json


.. code-block::
    :caption: out-pretty.json

    [
        {
            "input_data_id": "input1",
            "project_id": "prj1",
            "organization_id": "org1",
            "input_data_set_id": ",12345678-abcd-1234-abcd-1234abcd5678",
            "input_data_name": "data1",
            "input_data_path": "s3://af-production-input/organizations/...",
            "url": "https://annofab.com/organizations/...",
            "etag": "...",
            "updated_datetime": "2021-01-04T21:21:28.169+09:00",
            "original_input_data_path": "s3://af-production-input/organizations/...",
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


Usage Details
=================================

.. argparse::
    :ref: annofabcli.input_data.download_input_data_json.add_parser
    :prog: annofabcli input_data download
    :nosubcommands:
    :nodefaultconst:


