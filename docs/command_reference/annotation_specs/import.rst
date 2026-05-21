====================================================================================
annotation_specs import
====================================================================================

Description
=================================
アノテーション仕様の情報をJSON形式でインポートします。
``annotation_specs export`` コマンドで出力したJSONを利用できます。

既存アノテーションに影響する変更を防ぐため、以下の条件に該当する場合はインポートを中止します。

* 削除対象のラベルがアノテーションで使われている
* 種類変更対象のラベルがアノテーションで使われている
* 削除対象の属性を含むラベルがアノテーションで使われている
* 種類変更対象の属性を含むラベルがアノテーションで使われている
* 属性が削除されるラベルがアノテーションで使われている
* 削除対象の選択肢がアノテーションで使われている

既存アノテーションに影響することを理解した上でアノテーション仕様を変更する場合は、 ``--allow_affecting_annotations`` を指定してください。


Examples
=================================

基本的な使い方
--------------------------


.. code-block::

    $ annofabcli annotation_specs import --project_id prj1 --annotation_specs_json_file annotation_specs.json


``annotation_specs export`` と組み合わせる場合
------------------------------------------------------------


.. code-block::

    $ annofabcli annotation_specs export --project_id src_prj --out annotation_specs.json --format pretty_json
    $ annofabcli annotation_specs import --project_id dest_prj --annotation_specs_json_file annotation_specs.json


既存アノテーションに影響する変更を許可する場合
------------------------------------------------------------


.. code-block::

    $ annofabcli annotation_specs import --project_id prj1 --annotation_specs_json_file annotation_specs.json --allow_affecting_annotations


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.import_annotation_specs.add_parser
   :prog: annofabcli annotation_specs import
   :nosubcommands:
   :nodefaultconst:
