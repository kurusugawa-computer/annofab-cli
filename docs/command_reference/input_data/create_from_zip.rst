=================================
input_data put_with_zip
=================================

Description
=================================
zipファイルを入力データとして登録します。


Examples
=================================


基本的な使い方
--------------------------------------
画像や動画ファイルが格納されたzipファイルから、入力データを作成します。
``--zip`` にzipファイルのパスを指定してください。

.. code-block::

    $ annofabcli input_data put_with_zip --project_id prj1 --zip input_data.zip


デフォルトでは、入力データ名の先頭にはzipファイルのパスになります。別の名前を付ける場合は、``--input_data_name_prefix`` を指定してください。


.. code-block::

    $ annofabcli input_data put --project_id prj1 --zip input_data.zip \
    --input_data_name_prefix foo.zip



``--wait`` を指定すると、入力データの作成が完了するまで待ちます。


.. code-block::

    $ annofabcli input_data put --project_id prj1 --zip input_data.zip --wait





Usage Details
=================================

.. argparse::
   :ref: annofabcli.input_data.put_input_data_with_zip.add_parser
   :prog: annofabcli input_data put_with_zip
   :nosubcommands:
   :nodefaultconst:


