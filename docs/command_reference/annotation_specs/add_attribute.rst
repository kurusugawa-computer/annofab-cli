==========================================
annotation_specs add_attribute
==========================================

Description
=================================
アノテーション仕様に属性を追加し、指定したラベルへ紐付けます。 ``choice`` と ``select`` の場合は、選択肢も同時に追加します。


Examples
=================================

チェックボックス属性を追加する場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_attribute \
     --project_id prj1 \
     --attribute_type flag \
     --attribute_name_en unclear \
     --attribute_name_ja 不明 \
     --label_name_en car bus


JSON形式で選択肢を指定する場合
----------------------------------------------

.. code-block:: json
    :caption: choices.json

    [
        {
            "choice_id": "front",
            "choice_name_en": "front",
            "choice_name_ja": "前",
            "is_default": true
        },
        {
            "choice_name_en": "rear",
            "choice_name_ja": "後ろ",
            "is_default": false
        }
    ]


.. code-block::

    $ annofabcli annotation_specs add_attribute \
     --project_id prj1 \
     --attribute_type choice \
     --attribute_name_en direction \
     --choices_json file://choices.json \
     --label_name_en car bus


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_attribute.add_parser
    :prog: annofabcli annotation_specs add_attribute
    :nosubcommands:
    :nodefaultconst:
