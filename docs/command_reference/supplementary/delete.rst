=================================
supplementary delete
=================================

Description
=================================
補助情報を削除します。


Examples
=================================


基本的な使い方
--------------------------


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

    $ annofabcli supplementary delete --project_id prj1 --csv supplementary_data.csv


補助情報を指定して削除する(JSON)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

JSON形式で指定された補助情報を削除します。

以下は、JSONのサンプルです。


.. code-block::
    :caption: supplementary.json

    [
        {
            "input_data_id": "input1",
            "supplementary_data_id": "supplementary1",
        },
        {
            "input_data_id": "input2",
            "supplementary_data_id": "supplementary2",
        },
    ]


JSONのキーは、 ``--csv`` に指定するCSVファイルの列に対応します。
``--json`` にJSON形式の文字列、またはJSONファイルのパスを指定できます。

.. code-block::

    $ annofabcli supplementary delete --project_id prj1 --json file://input_data.json


入力データに紐づく全ての補助情報を削除する
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
``--input_data_id`` に入力データのinput_data_idを指定すると、入力データに紐づく全ての補助情報を削除します。


.. code-block::

    $ annofabcli supplementary delete --project_id prj1 --input_data_id input1 input2



Usage Details
=================================

.. argparse::
   :ref: annofabcli.supplementary.delete_supplementary_data.add_parser
   :prog: annofabcli supplementary delete
   :nosubcommands:
   :nodefaultconst:
