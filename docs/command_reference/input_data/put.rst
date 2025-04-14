=================================
input_data put
=================================

Description
=================================
入力データを作成します。


Examples
=================================


CSVファイルを指定する場合
--------------------------------------

入力データ情報が記載されたCSVファイルを元に、入力データを作成します。

CSVのフォーマットは以下の通りです。

* カンマ区切り
* ヘッダ行なし


.. csv-table::
   :header: 列番号,名前,必須,備考

    1列目,input_data_name,Yes,
    2列目,input_data_path,Yes,先頭が ``file://`` の場合、ローカルのファイルを入力データに使用します。
    3列目,input_data_id,No,省略した場合はinput_data_nameに近い値（IDに使えない文字を加工した値）になります。

各項目の詳細は `AnnofabのWebAPIドキュメント <https://annofab.com/docs/api/#operation/putInputData>`_ を参照してください。

以下はCSVファイルのサンプルです。

.. code-block::
    :caption: input_data.csv

    data1,s3://example.com/data1,id1,
    data2,s3://example.com/data2,id2,true
    data3,s3://example.com/data3,id3,false
    data4,https://example.com/data4,,
    data5,file://sample.jpg,,
    data6,file:///tmp/sample.jpg,,

.. warning::

    プライベートストレージが利用可能な組織配下のプロジェクトでしか、 ``input_data_path`` に ``https`` または ``s3`` スキームを利用できません。
    プライベートストレージを利用するには、Annofabサポート窓口への問い合わせが必要です。
    詳細は https://annofab.readme.io/docs/external-storage を参照してください。


``--csv`` に、CSVファイルのパスを指定してください。

.. code-block::

    $ annofabcli input_data put --project_id prj1 --csv input_data.csv


input_data_idが一致する入力データが既に存在する場合、デフォルトではスキップします。入力データを上書きする場合は、 ``--overwrite`` を指定してください。


.. code-block::
    
    $ annofabcli input_data put --project_id prj1 --csv input_data.csv --overwrite





JSON文字列を指定する場合
--------------------------------------

入力データ情報が記載されたJSONファイルを元に、入力データを作成します。

以下は、JSONのサンプルです。

.. code-block::
    :caption: input_data.json

    [
        {
            "input_data_name":"data1",
            "input_data_path":"file://sample.jpg"
        },
        {
            "input_data_name":"data2",
            "input_data_path":"s3://example.com/data2",
            "input_data_id":"id2",
            "sign_required": false
        }
    ]

JSONのキーは、``--csv`` に指定するCSVファイルの列に対応します。

``--json`` にJSON形式の文字列、またはJSONファイルのパスを指定できます。

.. code-block::

    $ annofabcli input_data put --project_id prj1 --json file://input_data.json



並列処理
----------------------------------------------

``--csv`` を指定したときは、並列実行が可能です。

.. code-block::

    $ annofabcli input_data put --project_id prj1 --csv input_data.csv
    --parallelism 4 --yes

Usage Details
=================================

.. argparse::
   :ref: annofabcli.input_data.put_input_data.add_parser
   :prog: annofabcli input_data put
   :nosubcommands:
   :nodefaultconst:


