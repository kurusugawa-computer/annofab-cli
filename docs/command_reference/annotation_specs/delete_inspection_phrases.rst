==================================================
annotation_specs delete_inspection_phrases
==================================================

Description
=================================
アノテーション仕様の定型指摘を複数件削除します。

``--inspection_phrase_id`` に削除対象のIDを複数指定します。
``file://`` を先頭に付けると、1行に1つのIDを記載した一覧ファイルを指定できます。
``--comment`` と ``--yes`` は :doc:`add_inspection_phrases` を参照してください。

存在しないID、入力内のID重複、空の入力はエラーにします。
全件を検証してから確認し、アノテーション仕様を1回で保存します。
定型指摘を参照する既存の検査コメントは書き換えません。
使用済みのIDを削除すると、そのIDの本文を現在のアノテーション仕様から取得できなくなります。

Examples
=================================

.. code-block:: bash

    $ annofabcli annotation_specs delete_inspection_phrases \
      --project_id prj1 \
      --inspection_phrase_id wrong_label out_of_position

.. code-block:: bash

    $ annofabcli annotation_specs delete_inspection_phrases \
      --project_id prj1 \
      --inspection_phrase_id file://inspection_phrase_ids.txt

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.delete_inspection_phrases.add_parser
    :prog: annofabcli annotation_specs delete_inspection_phrases
    :nosubcommands:
    :nodefaultconst:
