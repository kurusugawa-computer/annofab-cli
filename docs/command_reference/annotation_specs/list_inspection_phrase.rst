==========================================
annotation_specs list_inspection_phrase
==========================================

Description
=================================
アノテーション仕様の定型指摘情報を出力します。


Examples
=================================

基本的な使い方
--------------------------

.. code-block::

    $ annofabcli annotation_specs list_inspection_phrase --project_id prj1

デフォルトでは最新のアノテーション仕様を出力します。過去のアノテーション仕様を出力する場合は、``--before`` または ``--history_id`` を指定してください。
history_idは、`annofabcli annotation_specs list_history <../annotation_specs/list_history.html>`_ コマンドで取得できます。

以下のコマンドは、最新より1つ前のアノテーション仕様を出力します。

.. code-block::

    $ annofabcli annotation_specs list_inspection_phrase --project_id prj1 --before 1


以下のコマンドは、history_idが"xxx"のアノテーション仕様を出力します。

.. code-block::

    $ annofabcli annotation_specs list_inspection_phrase --project_id prj1 --history_id xxx


出力結果
=================================

JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs list_inspection_phrase --project_id prj1 --format pretty_json --output out.json


.. code-block::
    :caption: out.json

    [
        {
            "inspection_phrase_id": "phrase_blur",
            "inspection_phrase_text_en": "blurred",
            "inspection_phrase_text_ja": "ぼやけています",
            "inspection_phrase_text_vi": "mo"
        }
    ]


* ``inspection_phrase_id`` : 定型指摘ID
* ``inspection_phrase_text_en`` : 定型指摘の本文（英語）
* ``inspection_phrase_text_ja`` : 定型指摘の本文（日本語）
* ``inspection_phrase_text_vi`` : 定型指摘の本文（ベトナム語）


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.list_annotation_specs_inspection_phrase.add_parser
   :prog: annofabcli annotation_specs list_inspection_phrase
   :nosubcommands:
   :nodefaultconst:
