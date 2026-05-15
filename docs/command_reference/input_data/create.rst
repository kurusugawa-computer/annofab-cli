=================================
input_data create
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
* ヘッダ行あり


.. csv-table::
   :header: 列名,必須,備考

    input_data_name,Yes,
    input_data_path,Yes,先頭が ``file://`` の場合、ローカルのファイルを入力データに使用します。
    input_data_id,No,省略した場合はinput_data_nameに近い値（IDに使えない文字を加工した値）になります。

以下はCSVファイルのサンプルです。

.. code-block::
    :caption: input_data.csv

    input_data_name,input_data_path,input_data_id
    data1,s3://example.com/data1,id1
    data2,s3://example.com/data2,id2
    data3,https://example.com/data3,
    data4,file://sample.jpg,
    data5,file:///tmp/sample.jpg,


``--csv`` に、CSVファイルのパスを指定してください。

.. code-block::

    $ annofabcli input_data create --project_id prj1 --csv input_data.csv


共通のオプションやJSON形式の指定方法、上書き、並列実行については :doc:`put` を参照してください。


Usage Details
=================================

.. argparse::
   :ref: annofabcli.input_data.create_input_data.add_parser
   :prog: annofabcli input_data create
   :nosubcommands:
   :nodefaultconst:
