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

``--csv`` に、削除する補助情報が記載されたCSVファイルのパスを指定してください。

CSVのフォーマットは以下の通りです。

* カンマ区切り
* ヘッダ行なし


.. csv-table::
   :header: 列番号,名前,必須,備考

    1列目,input_data_id,Yes,
    2列目,supplementary_data_id,Yes,
    

以下はCSVファイルのサンプルです。

.. code-block::
    :caption: supplementary_data.csv

    input1,supplementary1
    input1,supplementary2
    input2,supplementary3



.. code-block::

    $ annofabcli supplementary delete --project_id prj1 --csv supplementary_data.csv

Usage Details
=================================

.. argparse::
   :ref: annofabcli.supplementary.delete_supplementary_data.add_parser
   :prog: annofabcli supplementary delete
   :nosubcommands:
