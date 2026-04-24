==========================================
annotation_specs add_label
==========================================

Description
=================================
アノテーション仕様にラベルを1件追加します。
v1では属性の紐付けは行わず、空の属性一覧を持つラベルを作成します。


Examples
=================================

基本的な使い方
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_label \
     --project_id prj1 \
     --label_name_en pedestrian \
     --annotation_type bounding_box


色とlabel_idを明示する場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_label \
     --project_id prj1 \
     --label_name_en road \
     --label_name_ja 路面 \
     --annotation_type segmentation_v2 \
     --label_id road_label \
     --color '#00CCFF'


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_label.add_parser
    :prog: annofabcli annotation_specs add_label
    :nosubcommands:
    :nodefaultconst:
