==========================================
annotation list
==========================================

Description
=================================
保留コメント一覧ファイルをダウンロードします。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドを実行すると、保留コメントの一覧ファイルがダウンロードされます。
アノテーションZIPのフォーマットについては https://annofab.com/docs/api/#section/Comment を参照してください。

.. code-block::

    $ annofabcli comment list --project_id prj1 --task_id task1 task2 --output comment.json



Usage Details
=================================

.. argparse::
    :ref: annofabcli.comment.list_comment.add_parser
    :prog: annofabcli comment list
    :nosubcommands:
    :nodefaultconst:


