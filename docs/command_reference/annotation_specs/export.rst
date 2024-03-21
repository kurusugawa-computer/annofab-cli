====================================================================================
annotation_specs export
====================================================================================

Description
=================================
アノテーション仕様の情報をJSON形式でエクスポートします。
このJSONは、`アノテーション仕様のインポート機能 <https://annofab.readme.io/docs/annotation-specs#%E3%82%A4%E3%83%B3%E3%83%9D%E3%83%BC%E3%83%88>`_ で利用できます。


Examples
=================================

基本的な使い方
--------------------------


.. code-block::

    $ annofabcli annotation_specs export --project_id prj1 --out out.json --format pretty_json




.. code-block::
    :caption: out.json

    {
        "labels": [
            "label_id": "763e1659-94c8-4424-9fc8-11b8fbcb115f",
            "label_name": {...},
            ...
        ],
        "additionals": [...],
        ...
    }


.. warning::

    ``annotation_specs export`` コマンドの出力結果は、アノテーション仕様のインポート機能で利用することを目的として作られています。

    JSON構造は、将来変更される可能性があります。
    ``annotation_specs export`` コマンドの出力結果であるJSONの構造に直接依存したプログラムを作成する場合は、ご注意ください。




Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.export_annotation_specs.add_parser
   :prog: annofabcli annotation_specs export
   :nosubcommands:
   :nodefaultconst:

