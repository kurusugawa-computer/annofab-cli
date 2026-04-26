==========================================
annotation_specs add_labels
==========================================

Description
=================================
アノテーション仕様にラベルを複数件追加します。


Examples
=================================

JSON形式で指定する場合
----------------------------------------------

.. code-block:: json
    :caption: labels.json

    [
        {
            "label_name_en": "pedestrian"
        },
        {
            "label_id": "bicycle",
            "label_name_en": "bicycle",
            "label_name_ja": "自転車"
        }
    ]


.. code-block::

    $ annofabcli annotation_specs add_labels \
     --project_id prj1 \
     --label_json file://labels.json \
     --annotation_type bounding_box


CSV形式で指定する場合
----------------------------------------------

.. code-block::
    :caption: labels.csv

    label_id,label_name_en,label_name_ja
    ,pedestrian,
    bicycle,bicycle,自転車


.. code-block::

    $ annofabcli annotation_specs add_labels \
     --project_id prj1 \
     --label_csv labels.csv \
     --annotation_type segmentation_v2


Usage Details
=================================

``label_name_en`` は必須です。 ``label_id`` と ``label_name_ja`` は任意です。

``--annotation_type`` の値は、``annotation_specs add_label`` の :ref:`annotation_specs_add_label_annotation_type_values` を参照してください。

.. argparse::
    :ref: annofabcli.annotation_specs.add_labels.add_parser
    :prog: annofabcli annotation_specs add_labels
    :nosubcommands:
    :nodefaultconst:
