==========================================
annotation_specs add_choices_to_attribute
==========================================

Description
=================================
既存の ``choice`` （ラジオボタン）または ``select`` （ドロップダウン）の属性に、選択肢を追加します。
指定する選択肢の ``choice_id`` と ``choice_name_en`` は、それぞれユニークである必要があります。


Examples
=================================

JSON形式で指定する場合
----------------------------------------------

.. code-block:: json
    :caption: choices.json

    [
        {
            "choice_id": "xlarge",
            "choice_name_en": "xlarge",
            "choice_name_ja": "特大"
        },
        {
            "choice_id": "tiny",
            "choice_name_en": "tiny",
            "choice_name_ja": "極小"
        }
    ]


.. code-block::

    $ annofabcli annotation_specs add_choices_to_attribute \
     --project_id prj1 \
     --attribute_name_en type \
     --choices_json file://choices.json


CSV形式で指定する場合
----------------------------------------------

.. code-block::
    :caption: choices.csv

    choice_id,choice_name_en,choice_name_ja,is_default
    xlarge,xlarge,特大,false
    tiny,tiny,極小,false


.. code-block::

    $ annofabcli annotation_specs add_choices_to_attribute \
     --project_id prj1 \
     --attribute_id 71620647-98cf-48ad-b43b-4af425a24f32 \
     --choices_csv choices.csv


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_choices_to_attribute.add_parser
    :prog: annofabcli annotation_specs add_choices_to_attribute
    :nosubcommands:
    :nodefaultconst:
