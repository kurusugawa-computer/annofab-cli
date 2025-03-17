=================================
input_data change_name
=================================

Description
=================================
入力データ名を変更します。


Examples
=================================




CSVファイルを指定する場合
--------------------------------------
``--csv`` に、変更対象の入力データ情報が記載されたCSVファイルのパスを指定してください。

CSVのフォーマットは以下の通りです。

* カンマ区切り
* ヘッダ行あり

.. csv-table::
   :header: 列名,必須,備考

    input_data_id,Yes,
    input_data_name,Yes,変更後の入力データ名


以下はCSVファイルのサンプルです。

.. code-block::
    :caption: input_data.csv

    input_data_id,input_data_name
    id1,new_name1
    id2,new_name2



.. code-block::

    $ annofabcli input_data change_name --project_id prj1 --csv input_data.csv






JSON文字列を指定する場合
--------------------------------------
``--json`` に、変更対象の入力データ情報をJSON文字列で指定してください。

以下は、JSONのサンプルです。

.. code-block::
    :caption: input_data.json

    [
        {
            "input_data_id":"id1",
            "input_data_name":"new_name1",
        },
        {
            "input_data_id":"id2",
            "input_data_name":"new_name2",
        }
    ]

JSONのキーは、``--csv`` に指定するCSVファイルの列に対応します。

``--json`` にJSON形式の文字列、またはJSONファイルのパスを指定できます。

.. code-block::

    $ annofabcli input_data put --project_id prj1 --json file://input_data.json




並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $ annofabcli input_data change_name --project_id prj1 \
     --csv input_data.csv --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.input_data.change_input_data_name.add_parser
   :prog: annofabcli input_data change_name
   :nosubcommands:
   :nodefaultconst:
