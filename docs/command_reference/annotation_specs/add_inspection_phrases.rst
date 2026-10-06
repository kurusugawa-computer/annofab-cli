==================================================
annotation_specs add_inspection_phrases
==================================================

Description
=================================
アノテーション仕様の定型指摘を複数件追加します。

入力形式
=================================
``--inspection_phrase_json`` または ``--inspection_phrase_csv`` のどちらか一方を指定します。
JSONは配列形式、CSVはヘッダー付きです。項目名は :doc:`list_inspection_phrase` の出力と共通です。

* ``inspection_phrase_id`` （必須）：定型指摘ID。英数字・アンダースコア・ハイフンのみ使用でき、自動生成しません。
* ``inspection_phrase_text_ja`` （任意）：日本語本文。
* ``inspection_phrase_text_en`` （任意）：英語本文。
* ``inspection_phrase_text_vi`` （任意）：ベトナム語本文。

本文は、いずれかの言語で1つ以上指定する必要があります。
省略、 ``null`` 、空文字、空白だけの本文は未指定として扱います。未指定の言語への補完は行いません。
追加時の表示用の既定言語は、指定された言語から日本語・英語・ベトナム語の優先順で選びます。

既存IDとの衝突、入力内のID重複、空の入力、未知の入力項目はエラーにします。
全件を検証してから確認し、アノテーション仕様を1回で保存します。
``--comment`` で変更コメントを指定できます。省略時は自動生成します。 ``--yes`` で実行前の確認を省略できます。

Examples
=================================
JSONで追加する
----------------------------------------------

.. code-block:: bash

    $ annofabcli annotation_specs add_inspection_phrases \
      --project_id prj1 \
      --inspection_phrase_json '[{"inspection_phrase_id":"wrong_label","inspection_phrase_text_en":"Wrong label"}]'

JSONファイルの場合は ``--inspection_phrase_json file://inspection_phrases.json`` と指定します。

CSVで追加する
----------------------------------------------

.. code-block:: text
    :caption: inspection_phrases.csv

    inspection_phrase_id,inspection_phrase_text_ja,inspection_phrase_text_en,inspection_phrase_text_vi
    wrong_label,ラベルが間違っています,Wrong label,
    out_of_position,位置がずれています,,

.. code-block:: bash

    $ annofabcli annotation_specs add_inspection_phrases \
      --project_id prj1 \
      --inspection_phrase_csv inspection_phrases.csv

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_inspection_phrases.add_parser
    :prog: annofabcli annotation_specs add_inspection_phrases
    :nosubcommands:
    :nodefaultconst:
