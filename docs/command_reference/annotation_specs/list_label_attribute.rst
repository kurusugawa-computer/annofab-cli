==========================================
annotation_specs list_label_attribute
==========================================

Description
=================================
アノテーション仕様のラベルとラベルに含まれている属性の一覧を出力します。

Examples
=================================


.. code-block::

    $ annofabcli annotation_specs list_label_attribute --project_id prj1


出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs list_label_attribute --project_id prj1 --format csv --output out.csv

.. code-block::
    :caption: out.json
    
    [
    {
        "label_id": "a0a0c27b-dad8-42da-9235-c09688cdfd12",
        "label_name_en": "car",
        "label_name_ja": "car",
        "label_name_vi": "car",
        "annotation_type": "bounding_box",
        "attribute_id": "0f739b17-c22b-4f4a-a791-d142eb0bcd41",
        "attribute_name_en": "truncation",
        "attribute_name_ja": "truncation",
        "attribute_name_vi": "truncation",
        "attribute_type": "flag"
    },
    {
        "label_id": "53530a8f-e48f-46e9-833f-8e48becb25af",
        "label_name_en": "road",
        "label_name_ja": "road",
        "label_name_vi": "road",
        "annotation_type": "segmentation_v2",
        "attribute_id": "0f739b17-c22b-4f4a-a791-d142eb0bcd41",
        "attribute_name_en": "truncation",
        "attribute_name_ja": "truncation",
        "attribute_name_vi": "truncation",
        "attribute_type": "flag"
    }
    ]
        

* ``label_id`` : ラベルID
* ``label_name_en`` : ラベル名（英語）
* ``label_name_ja`` : ラベル名（日本語）
* ``label_name_vi`` : ラベル名（ベトナム語）
* ``annotation_type`` : アノテーションの種類
* ``attribute_id`` : 属性ID
* ``attribute_name_en`` : 属性名（英語）
* ``attribute_name_ja`` : 属性名（日本語）
* ``attribute_name_vi`` : 属性名（ベトナム語）
* ``attribute_type`` : 属性の種類


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.list_annotation_specs_label_attribute.add_parser
   :prog: annofabcli annotation_specs list_label_attribute
   :nosubcommands:
   :nodefaultconst:
