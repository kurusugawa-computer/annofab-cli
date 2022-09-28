==========================================
inspection_comment download
==========================================

Description
=================================
検査コメント全件ファイルをダウンロードします。


.. warning::

    非推奨なコマンドです。2022-12-01以降に廃止する予定です。
    替わりに `annofabcli comment download <../comment/download.html>`_ コマンドを利用してください。


Examples
=================================


基本的な使い方
--------------------------

以下のコマンドを実行すると、検査コメント全件ファイルがダウンロードされます。

.. code-block::

    $ annofabcli inspection_comment download --project_id prj1 --output comment.json

作成した検査コメントは、02:00(JST)頃にコメント全件ファイルに反映されます。





Usage Details
=================================

.. argparse::
    :ref: annofabcli.comment.download_comment_json.add_parser
    :prog: annofabcli comment download
    :nosubcommands:
    :nodefaultconst:


