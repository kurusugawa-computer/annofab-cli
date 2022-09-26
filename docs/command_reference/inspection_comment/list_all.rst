==========================================
inspection_comment list_all
==========================================

Description
=================================
すべての検査コメンの一覧を出力します。


.. warning::

    非推奨なコマンドです。2022-12-01以降に廃止する予定です。
    替わりに `annofabcli comment list_all <../comment/list_all.html>`_ コマンドを使用してください。

    



Examples
=================================


基本的な使い方
--------------------------

以下のコマンドは、検査コメント全件ファイルをダウンロードしてから、検査コメント一覧を出力します。

.. code-block::

    $ annofabcli inspection_comment list_all --project_id prj1

.. code-block::

    $ annofabcli inspection_comment list_all --project_id prj1 --inspection_comment_json inspection_comment.json


絞り込み
--------------------------
以下のコマンドは、返信コメントを除外した検査コメントを出力します。

.. code-block::

    $ annofabcli inspection_comment list_all --project_id prj1  --exclude_reply


以下のコマンドは、返信コメントのみを出力します。

.. code-block::

    $ annofabcli inspection_comment list_all --project_id prj1  --only_reply





出力結果
=================================
`annofabcli inspection_comment list <../inspection_comment/list.html>`_ コマンドの出力結果と同じです。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.inspection_comment.list_all_inspection_comment.add_parser
   :prog: annofabcli inspection_comment list_all
   :nosubcommands:
   :nodefaultconst:


See also
=================================
* `annofabcli inspection_comment list <../inspection_comment/list.html>`_
