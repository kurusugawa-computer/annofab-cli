==========================================
annotation_specs add_attributes
==========================================

Description
=================================
アノテーション仕様に複数の非選択肢系属性を追加します。


Examples
=================================

JSON形式で指定する場合
----------------------------------------------

.. code-block:: json
    :caption: attributes.json

    [
        {
            "attribute_type": "flag",
            "attribute_name_en": "unclear",
            "label_name_ens": ["car", "bus"]
        },
        {
            "attribute_type": "text",
            "attribute_name_en": "comment2",
            "label_name_ens": ["bike"]
        }
    ]

.. code-block::

    $ annofabcli annotation_specs add_attributes \
     --project_id prj1 \
     --attribute_json file://attributes.json


--attribute_json の構造
=================================

``--attribute_json`` には、属性情報のJSON配列を指定します。各要素は1件の属性を表すJSONオブジェクトです。

各属性オブジェクトでは、以下のキーを指定できます。

* ``attribute_type`` : 必須。属性の種類。指定できる値は :ref:`annotation_specs_non_choice_attribute_types` を参照してください。
* ``attribute_name_en`` : 必須。属性名（英語）。
* ``label_name_ens`` : ``label_ids`` とどちらか一方が必須。属性を追加する対象ラベルの英語名一覧。
* ``label_ids`` : ``label_name_ens`` とどちらか一方が必須。属性を追加する対象ラベルの ``label_id`` 一覧。
* ``attribute_name_ja`` : 任意。属性名（日本語）。
* ``attribute_id`` : 任意。属性ID。未指定の場合はUUIDv4が自動生成されます。


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_attributes.add_parser
    :prog: annofabcli annotation_specs add_attributes
    :nosubcommands:
    :nodefaultconst:
