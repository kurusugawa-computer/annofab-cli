==========================================
comment list_all
==========================================

Description
=================================
すべてのコメント一覧を出力します。


.. note::

    コメント一覧は、コマンドを実行した日の02:00(JST)頃の状態です。
    最新のコメント情報を取得したい場合は、 ``annofabcli comment list`` コマンドを実行してください。



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドを実行すると、すべてのコメント（検査コメントまたは保留コメント）の一覧が出力されます。

.. code-block::

    $ annofabcli comment list_all --project_id prj1


``annofabcli comment download`` コマンドの出力結果であるコメント全件ファイルも指定することができます。


.. code-block::

    $ annofabcli comment download --project_id prj1 --output comment.json

    $ annofabcli comment list_all --project_id prj1 --comment_json comment.json


出力結果
=================================
`annofabcli comment list <../comment/list.html>`_ コマンドの出力結果と同じです。



Usage Details
=================================

.. argparse::
    :ref: annofabcli.comment.list_comment.add_parser
    :prog: annofabcli comment list
    :nosubcommands:
    :nodefaultconst:
