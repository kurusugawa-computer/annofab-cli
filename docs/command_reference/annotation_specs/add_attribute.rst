==========================================
annotation_specs add_attribute
==========================================

Description
=================================
アノテーション仕様に非選択肢系の属性を追加し、指定したラベルへ紐付けます。 ``choice`` と ``select`` を追加する場合は、 ``annotation_specs add_choice_attribute`` を使用してください。


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

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_attribute.add_parser
    :prog: annofabcli annotation_specs add_attribute
    :nosubcommands:
    :nodefaultconst:
