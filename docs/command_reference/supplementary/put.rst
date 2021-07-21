=================================
supplementary put
=================================

Description
=================================
補助情報を作成します。



Examples
=================================


CSVから補助情報を登録する
--------------------------------------
補助情報が記載されたCSVファイルを元に、補助情報を登録します。


CSVのフォーマットは以下の通りです。

* カンマ区切り
* ヘッダ行なし

.. csv-table::
   :header: 列番号,名前,必須,備考

    1列目,input_data_id,Yes,
    2列目,supplementary_data_number,Yes,表示順を表す数値を指定してください。
    3列目,supplementary_data_name,Yes,
    4列目,supplementary_data_path,Yes,先頭が ``file://`` の場合、ローカルのファイルを補助情報に使用します。
    5列目,supplementary_data_id,No,省略した場合はUUID(v4)になります。
    6列目,supplementary_data_type,No,``image`` , ``text`` または ``custom`` を指定ください。省略した場合は、ファイル名から推測します。

以下はCSVファイルのサンプルです。

.. code-block::
    :caption: supplementary_data.csv

    input1,1,data1-1,s3://example.com/data1,id1,
    input1,2,data1-2,s3://example.com/data2,id2,image
    input1,3,data1-3,s3://example.com/data3,id3,text
    input2,1,data2-1,https://example.com/data4,,
    input2,2,data2-2,file://sample.jpg,,
    input2,3,data2-3,file:///tmp/sample.jpg,,


``--csv`` に、CSVファイルのパスを指定してください。

.. code-block::

    $ annofabcli supplementary put --project_id prj1 --csv supplementary_data.csv


supplementary_data_id（省略時は supplementary_data_number）が一致する補助情報が既に存在する場合は、デフォルトではスキップします。補助情報を上書きする場合は、 ``--overwrite`` を指定してください。

.. code-block::
    
    $ annofabcli supplementary put --project_id prj1 --csv supplementary_data.csv --overwrite


JSONから補助情報を登録する
--------------------------------------
補助情報が記載されたJSONファイルを元に、補助情報を登録します。


以下は、JSONのサンプルです。




.. code-block::
    :caption: supplementary_data.json

    [
        
        {
            "input_data_id": "input1",
            "supplementary_data_number": 1,
            "supplementary_data_name": "foo",
            "supplementary_data_path": "file://foo.jpg",
        }
        ,
        {
            "input_data_id": "input1",
            "supplementary_data_number": 2,
            "supplementary_data_name": "bar",
            "supplementary_data_path": "s3://example.com/bar.jpg",
            "supplementary_data_id": "id2",
            "supplementary_data_type": "image"
        }
    ]



JSONのキーは、``--csv`` に指定するCSVファイルの列に対応します。

``--json`` にJSON形式の文字列、またはJSONファイルのパスを指定できます。

.. code-block::

    $ annofabcli supplementary put --project_id prj1 --json file://supplementary_data.json

    

並列処理
----------------------------------------------

以下のコマンドは、並列数4で実行します。

.. code-block::

    $ annofabcli supplementary put --project_id prj1 --csv supplementary_data.csv
    --parallelism 4 --yes


