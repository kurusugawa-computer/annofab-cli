==========================================
inspection_comment list_with_json
==========================================

Description
=================================
検査コメント全件ファイルから検査コメント一覧を出力します。


Examples
=================================


基本的な使い方
--------------------------

以下のコマンドは、検査コメント全件ファイルをダウンロードしてから、検査コメント一覧を出力します。

.. code-block::

    $ annofabcli inspection_comment list_with_json --project_id prj1

検査コメント全件ファイルを指定する場合は、``--inspection_comment_json`` を指定してください。
検査コメント全件ファイルは、`annofabcli project download <../project/download.html>`_ コマンドでダウンロードできます。

.. code-block::

    $ annofabcli inspection_comment list_with_json --project_id prj1 --inspection_comment_json inspection_comment.json


絞り込み
--------------------------
以下のコマンドは、返信コメントを除外した検査コメントを出力します。

.. code-block::

    $ annofabcli inspection_comment list_with_json --project_id prj1  --exclude_reply


以下のコマンドは、返信コメントのみを出力します。

.. code-block::

    $ annofabcli inspection_comment list_with_json --project_id prj1  --only_reply





出力結果
=================================
`annofabcli inspection_comment list <../inspection_comment/list.html>`_ コマンドの出力結果と同じです。


.. argparse::
   :ref: annofabcli.inspection_comment.list_inspections_with_json.add_parser
   :prog: annofabcli inspection_comment list_with_json
   :nosubcommands:


See also
=================================
* `annofabcli project download <../project/download.html>`_
* `annofabcli inspection_comment list <../inspection_comment/list.html>`_
