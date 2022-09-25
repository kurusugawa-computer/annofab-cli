==========================================
input_data list_all
==========================================

Description
=================================
すべての入力データの一覧を出力します。

.. note::

    出力される入力データは、コマンドを実行した日の02:00(JST)頃の状態です（入力データ全件ファイルを明示的に更新しない限り）。
    最新の入力データを出力したい場合は、 ``--latest`` 引数を指定してください。




Examples
=================================




基本的な使い方
--------------------------

以下のコマンドは、入力データ全件ファイルをダウンロードしてから、入力データ一覧を出力します。

.. code-block::

    $ annofabcli input_data list_all --project_id prj1


入力データ全件ファイルを指定する場合は、``--input_data_json`` に入力データ全件ファイルのパスを指定してください。
入力データ全件ファイルは、 `annofabcli input_data download <../input_data/download.html>`_ コマンドでダウンロードできます。


.. code-block::

    $ annofabcli input_data list_all --project_id prj1 --input_data_json input_data.json 



絞り込み
----------------------------------------------

``--input_data_query`` を指定すると、入力データの名前や入力データのパスで絞り込めます。
以下のコマンドは、入力データ名に"sample"を含む入力データの一覧を出力します。

.. code-block::

    $ annofabcli input_data list_with_json --project_id prj1  \
     --input_data_query '{"input_data_name": "sample"}' 


以下に ``--input_data_query`` に利用できるキーと、絞り込みの内容を記載します。

* input_data_id : 入力データIDを部分一致で絞り込む（大文字小文字を区別しない）
* input_data_name : 入力データ名を部分一致で絞り込む（大文字小文字を区別しない）
* input_data_path : 入力データ名を部分一致で絞り込む


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
   :ref: annofabcli.input_data.list_all_input_data.add_parser
   :prog: annofabcli input_data list_all_input_data
   :nosubcommands:
   :nodefaultconst:


See also
=================================
* `annofabcli input_data list <../input_data/list.html>`_




