=====================
supplementary list
=====================

Description
=================================
補助情報一覧を出力します。


Examples
=================================

基本的な使い方
--------------------------

以下のコマンドは、指定した入力データに紐づく補助情報を出力します。

.. code-block::

    $ annofabcli supplementary list --project_id prj1 --input_data_id input1 input2

``--input_data_id`` を指定しない場合は、入力データ全件ファイルに記載されているすべての入力データに紐づく補助情報の一覧を出力します。

.. code-block::

    $ annofabcli supplementary list --project_id prj1



出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli supplementary list --format csv --output out.csv

`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/supplementary/list/out.csv>`_

JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli supplementary list --input_data_id file://input_data_id.txt --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
    {
        "project_id": "prj1",
        "organization_id": "org1",
        "input_data_id": "input1",
        "input_data_set_id": "12345678-abcd-1234-abcd-1234abcd5678",
        "supplementary_data_id": "supplementary1",
        "supplementary_data_name": "test-supplementary1",
        "supplementary_data_path": "s3://af-production-input/organizations/...",
        "supplementary_data_type": "image",
        "supplementary_data_number": 1,
        "updated_datetime": "2021-01-04T22:02:36.33+09:00"
    },
    ...
    ]

Usage Details
=================================

.. argparse::
   :ref: annofabcli.supplementary.list_supplementary_data.add_parser
   :prog: annofabcli supplementary list
   :nosubcommands:
   :nodefaultconst:
