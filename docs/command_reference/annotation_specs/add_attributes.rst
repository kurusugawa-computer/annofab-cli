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


--attribute_type に指定できる値
=================================

``add_attribute`` コマンドと同様です。 :ref:`annotation_specs_non_choice_attribute_types` を参照してください。


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_attributes.add_parser
    :prog: annofabcli annotation_specs add_attributes
    :nosubcommands:
    :nodefaultconst:
