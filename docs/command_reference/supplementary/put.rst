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

* ヘッダ行あり
* カンマ区切り

.. csv-table::
   :header: 列名,必須,備考

    input_data_id,Yes,
    supplementary_data_path,Yes,先頭が ``file://`` の場合、ローカルのファイルを補助情報に使用します。
    supplementary_data_name,Yes,
    supplementary_data_id,No,省略した場合はsupplementary_data_nameに近い値（IDに使えない文字を加工した値）になります。
    supplementary_data_type,No,補助情報の種類。 ``image`` 、 ``text`` または ``custom`` のいずれかを指定ください。省略した場合は、ファイル名から推測します。
    supplementary_data_number,Yes,補助情報の表示順

以下はCSVファイルのサンプルです。

.. code-block::
    :caption: supplementary_data.csv

    input_data_id,supplementary_data_name,supplementary_data_path,supplementary_data_id,supplementary_data_type,supplementary_data_number
    input1,data1-1,s3://example.com/data1,id1,
    input1,data1-2,s3://example.com/data2,id2,image,1
    input1,data1-3,s3://example.com/data3,id3,text,2
    input2,data2-1,https://example.com/data4,,
    input2,data2-2,file://sample.jpg,,
    input2,data2-3,file:///tmp/sample.jpg,,


.. warning::

    プライベートストレージが利用可能な組織配下のプロジェクトでしか、 ``input_data_path`` に ``https`` または ``s3`` スキームを利用できません。
    プライベートストレージを利用するには、Annofabサポート窓口への問い合わせが必要です。
    詳細は https://annofab.readme.io/docs/external-storage を参照してください。



``--csv`` に、CSVファイルのパスを指定してください。

.. code-block::

    $ annofabcli supplementary put --project_id prj1 --csv supplementary_data.csv


supplementary_data_idが一致する補助情報が既に存在する場合は、デフォルトではスキップします。補助情報を上書きする場合は、 ``--overwrite`` を指定してください。

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

Usage Details
=================================

.. argparse::
   :ref: annofabcli.supplementary.put_supplementary_data.add_parser
   :prog: annofabcli supplementary put
   :nosubcommands:
   :nodefaultconst:



