==========================================
annotation_specs add_labels
==========================================

Description
=================================
アノテーション仕様にラベルを複数件追加します。


Examples
=================================

ラベル名(英語)を複数指定する場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_labels \
     --project_id prj1 \
     --label_name_en pedestrian bicycle traffic_light \
     --annotation_type bounding_box


ファイルからラベル名(英語)一覧を読み込む場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_labels \
     --project_id prj1 \
     --label_name_en file://label_names.txt \
     --annotation_type segmentation_v2


Usage Details
=================================

``--annotation_type`` の値は、``annotation_specs add_label`` の :ref:`annotation_specs_add_label_annotation_type_values` を参照してください。

.. argparse::
    :ref: annofabcli.annotation_specs.add_labels.add_parser
    :prog: annofabcli annotation_specs add_labels
    :nosubcommands:
    :nodefaultconst:
