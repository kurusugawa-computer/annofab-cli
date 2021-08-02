=================================
input_data put
=================================

Description
=================================
入力データを作成します。


Examples
=================================


入力データを個別に作成する(CSV)
--------------------------------------

入力データ情報が記載されたCSVファイルを元に、入力データを作成します。

CSVのフォーマットは以下の通りです。

* カンマ区切り
* ヘッダ行なし


.. csv-table::
   :header: 列番号,名前,必須,備考

    1列目,input_data_name,Yes,
    2列目,input_data_path,Yes,先頭が ``file://`` の場合、ローカルのファイルを入力データに使用します。
    3列目,input_data_id,No,省略した場合はUUID(v4)になります。
    4列目,sign_required,No,``true`` または ``false`` を指定してください。省略した場合は ``null`` です。


以下はCSVファイルのサンプルです。

.. code-block::
    :caption: input_data.csv

    data1,s3://example.com/data1,id1,
    data2,s3://example.com/data2,id2,true
    data3,s3://example.com/data3,id3,false
    data4,https://example.com/data4,,
    data5,file://sample.jpg,,
    data6,file:///tmp/sample.jpg,,



``--csv`` に、CSVファイルのパスを指定してください。

.. code-block::

    $ annofabcli input_data put --project_id prj1 --csv input_data.csv


input_data_idが一致する入力データが既に存在する場合、デフォルトではスキップします。入力データを上書きする場合は、 ``--overwrite`` を指定してください。


.. code-block::
    
    $ annofabcli input_data put --project_id prj1 --csv input_data.csv --overwrite





入力データを個別に作成する(JSON)
--------------------------------------

入力データ情報が記載されたJSONファイルを元に、入力データを作成します。

以下は、JSONのサンプルです。

.. code-block::
    :caption: input_data.json

    [
        {
            "input_data_name":"data1",
            "input_data_path":"file://sample.jpg",
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



zipファイルから入力データを作成する
--------------------------------------
画像や動画ファイルが格納されたzipファイルから、入力データを作成します。
``--zip`` にzipファイルのパスを指定してください。

.. code-block::

    $ annofabcli input_data put --project_id prj1 --zip input_data.zip


デフォルトでは、入力データ名の先頭にはzipファイルのパスになります。別の名前を付ける場合は、``--input_data_name_for_zip`` を指定してください。


.. code-block::

    $ annofabcli input_data put --project_id prj1 --zip input_data.zip \
    --input_data_name_for_zip foo.zip



``--wait`` を指定すると、入力データの作成が完了するまで待ちます。


.. code-block::

    $ annofabcli input_data put --project_id prj1 --zip input_data.zip --wait





並列処理
----------------------------------------------

``--csv`` を指定したときは、並列実行が可能です。

.. code-block::

    $ annofabcli input_data put --project_id prj1 --csv input_data.csv
    --parallelism 4 --yes

