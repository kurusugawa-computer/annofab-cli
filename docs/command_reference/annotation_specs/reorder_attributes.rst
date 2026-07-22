==========================================
annotation_specs reorder_attributes
==========================================

Description
=================================
アノテーション仕様のラベル内の属性を並び替えます。

属性の並び順はラベルごとに管理されるため、対象ラベルを1件指定します。
指定した属性を指定順で先頭に移動します。
指定しなかった属性は現在の順番を維持します。


Examples
=================================

ラベル名と属性名を指定して並び替える
----------------------------------------------

以下のコマンドは、"car" ラベルに含まれる "unclear", "link" 属性をこの順番で先頭に移動します。
その他の属性は現在の順番を維持して、"unclear", "link" の後ろに並びます。

.. code-block::

    $ annofabcli annotation_specs reorder_attributes \
     --project_id prj1 \
     --label_name_en car \
     --attribute_name_en unclear link


ラベルIDと属性IDを指定して並び替える
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs reorder_attributes \
     --project_id prj1 \
     --label_id label_car \
     --attribute_id attribute_unclear attribute_link


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.reorder_attributes.add_parser
    :prog: annofabcli annotation_specs reorder_attributes
    :nosubcommands:
    :nodefaultconst:
