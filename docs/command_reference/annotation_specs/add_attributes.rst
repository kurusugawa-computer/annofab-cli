==========================================
annotation_specs add_attributes
==========================================

Description
=================================
アノテーション仕様に複数の非選択肢系属性を追加します。


Examples
=================================

以下のコマンドは、複数の属性を一度に追加します。

.. code-block::

    $ annofabcli annotation_specs add_attributes \
     --project_id prj1 \
     --attribute_json '[{"attribute_type":"flag","attribute_name_en":"unclear","label_name_en":["car","bus"]},{"attribute_type":"text","attribute_name_en":"comment2","label_name_en":["bike"]}]'


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_attributes.add_parser
    :prog: annofabcli annotation_specs add_attributes
    :nosubcommands:
    :nodefaultconst:
