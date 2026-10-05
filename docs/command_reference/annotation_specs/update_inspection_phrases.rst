==================================================
annotation_specs update_inspection_phrases
==================================================

Description
=================================
アノテーション仕様の定型指摘を複数件更新します。

入力項目、JSON・CSVの指定方法、共通引数は :doc:`add_inspection_phrases` を参照してください。

``inspection_phrase_id`` は既存の定型指摘IDを指定します。IDは変更できません。
本文は、更新する言語を1つ以上指定する必要があります。
指定した言語だけを更新し、省略、 ``null`` 、空文字、空白だけの本文は既存値を保持します。
本文の解除には対応していません。表示用の既定言語も保持します。
ただし既定言語に本文が存在しない場合は、本文が存在する言語に変更します。

存在しないID、入力内のID重複、空の入力、未知の入力項目はエラーにします。
全件を検証してから確認し、アノテーション仕様を1回で保存します。差分がなければ保存しません。
検査コメントは変更しません。

Examples
=================================
日本語本文を更新する
----------------------------------------------

.. code-block:: bash

    $ annofabcli annotation_specs update_inspection_phrases \
      --project_id prj1 \
      --inspection_phrase_json '[{"inspection_phrase_id":"wrong_label","inspection_phrase_text_ja":"ラベルを修正してください"}]'

一覧を編集して更新する
----------------------------------------------

.. code-block:: bash

    $ annofabcli annotation_specs list_inspection_phrase \
      --project_id prj1 --output inspection_phrases.csv

    # CSV内の本文を編集してから実行します。
    $ annofabcli annotation_specs update_inspection_phrases \
      --project_id prj1 --inspection_phrase_csv inspection_phrases.csv

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.update_inspection_phrases.add_parser
    :prog: annofabcli annotation_specs update_inspection_phrases
    :nosubcommands:
    :nodefaultconst:
