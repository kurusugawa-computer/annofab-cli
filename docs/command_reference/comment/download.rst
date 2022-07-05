==========================================
comment download
==========================================

Description
=================================
コメント全件ファイルをダウンロードします。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドを実行すると、コメント全件ファイルがダウンロードされます。

.. code-block::

    $ annofabcli comment download --project_id prj1 --output comment.json

作成したコメントは、02:00(JST)頃にコメント全件ファイルに反映されます。



Usage Details
=================================

.. argparse::
    :ref: annofabcli.comment.download_comment_json.add_parser
    :prog: annofabcli comment download
    :nosubcommands:
    :nodefaultconst:


