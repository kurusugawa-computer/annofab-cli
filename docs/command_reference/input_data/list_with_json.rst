==========================================
input_data list_with_json
==========================================

Description
=================================
入力データファイルから入力データ一覧を出力します。
10,000件以上の入力データを出力する際に利用できます。


Examples
=================================




基本的な使い方
--------------------------

以下のコマンドは、入力データ全件ファイルをダウンロードしてから、入力データ一覧を出力します。

.. code-block::

    $ annofabcli input_data list_with_json --project_id prj1


入力データ全件ファイルを指定する場合は、``--input_data_json`` に入力データ全件ファイルのパスを指定してください。
入力データ全件ファイルは、`annofabcli project download <../project/download.html>`_ コマンドでダウンロードできます。


.. code-block::

    $ annofabcli input_data list_with_json --project_id prj1 --input_data_json input_data.json 



絞り込み
----------------------------------------------

``--input_data_query`` を指定すると、入力データの名前や入力データのパスで絞り込めます。


以下のコマンドは、入力データ名に"sample"を含む入力データの一覧を出力します。

.. code-block::

    $ annofabcli input_data list_with_json --project_id prj1  \
     --input_data_query '{"input_data_name": "sample"}' 



``--input_data_id`` を指定すると、input_data_idに合致する入力データの一覧を出力します。

.. code-block::

    $ annofabcli input_data list_with_json --project_id prj1 \
     --input_data_id file://input_data_id.txt




出力結果
=================================
`annofabcli input_data list <../input_data/list.html>`_ コマンドの出力結果と同じです。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.input_data.list_input_data_with_json.add_parser
   :prog: annofabcli input_data list_with_json
   :nosubcommands:
   :nodefaultconst:


See also
=================================
* `annofabcli project download <../project/download.html>`_
* `annofabcli input_data list <../input_data/list.html>`_
