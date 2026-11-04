==========================================================
supplementary delete_per_supplementary_data
==========================================================

Description
=================================
``input_data_id`` と ``supplementary_data_id`` の一覧で個別指定した補助情報を削除します。
補助情報ごとに削除を確認します。

入力データに紐づくすべての補助情報を削除する場合は、:doc:`delete` を使用してください。
従来の ``supplementary delete --csv`` と ``--json`` は、このコマンドに移動しました。

Examples
=================================

補助情報を指定して削除する(CSV)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


``--csv`` に、削除する補助情報が記載されたCSVファイルのパスを指定してください。

CSVのフォーマットは以下の通りです。

* カンマ区切り
* ヘッダ行あり


.. csv-table::
   :header: 列名,必須,備考

    input_data_id,Yes,
    supplementary_data_id,Yes,


以下はCSVファイルのサンプルです。

.. code-block::
    :caption: supplementary_data.csv

    input_data_id,supplementary_data_id
    input1,supplementary1
    input1,supplementary2
    input2,supplementary3



.. code-block::

    $ annofabcli supplementary delete_per_supplementary_data --project_id prj1 --csv supplementary_data.csv


補助情報を指定して削除する(JSON)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

JSON形式で指定された補助情報を削除します。

以下は、JSONのサンプルです。


.. code-block::
    :caption: supplementary.json

    [
        {
            "input_data_id": "input1",
            "supplementary_data_id": "supplementary1"
        },
        {
            "input_data_id": "input2",
            "supplementary_data_id": "supplementary2"
        }
    ]


JSONのキーは、 ``--csv`` に指定するCSVファイルの列に対応します。
``--json`` にJSON形式の文字列、またはJSONファイルのパスを指定できます。

.. code-block::

    $ annofabcli supplementary delete_per_supplementary_data --project_id prj1 --json file://supplementary.json


Usage Details
=================================

.. argparse::
   :ref: annofabcli.supplementary.delete_supplementary_data_per_supplementary_data.create_parser
   :prog: annofabcli supplementary delete_per_supplementary_data
   :nosubcommands:
   :nodefaultconst:

See also
=================================
* :doc:`delete`
