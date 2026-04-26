==========================================
annotation_specs add_choice_attribute
==========================================

Description
=================================
アノテーション仕様に ``choice`` （ラジオボタン）または ``select`` （ドロップダウン）の選択肢系属性を追加し、指定したラベルへ紐付けます。


Examples
=================================

JSON形式で指定する場合
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

    $ annofabcli annotation_specs add_choice_attribute \
     --project_id prj1 \
     --attribute_type choice \
     --attribute_name_en direction \
     --choice_json file://choices.json \
     --label_name_en car bus \


CSV形式で指定する場合
----------------------------------------------

.. code-block::
    :caption: choices.csv

    choice_id,choice_name_en,choice_name_ja,is_default
    front,front,前,true
    rear,rear,後ろ,false


.. code-block::

    $ annofabcli annotation_specs add_choice_attribute \
     --project_id prj1 \
     --attribute_type select \
     --attribute_name_en direction \
     --choice_csv choices.csv \
     --label_id l1 l2


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_choice_attribute.add_parser
    :prog: annofabcli annotation_specs add_choice_attribute
    :nosubcommands:
    :nodefaultconst:
