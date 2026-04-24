==========================================
annotation_specs add_attribute
==========================================

Description
=================================
アノテーション仕様に非選択肢系の属性を追加します。


Examples
=================================

以下のコマンドは、"car", "bus"ラベルにチェックボックス属性を追加します。

.. code-block::

    $ annofabcli annotation_specs add_attribute \
     --project_id prj1 \
     --attribute_type flag \
     --attribute_name_en unclear \
     --label_name_en car bus

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_attribute.add_parser
    :prog: annofabcli annotation_specs add_attribute
    :nosubcommands:
    :nodefaultconst:
