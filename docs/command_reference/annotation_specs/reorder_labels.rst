==========================================
annotation_specs reorder_labels
==========================================

Description
=================================
アノテーション仕様のラベルを並び替えます。

指定したラベルを指定順で先頭に移動します。
指定しなかったラベルは現在の順番を維持します。


Examples
=================================

ラベル名を指定して並び替える
----------------------------------------------

以下のコマンドは、"bus", "car" ラベルをこの順番で先頭に移動します。
その他のラベルは現在の順番を維持して、"bus", "car" の後ろに並びます。

.. code-block::

    $ annofabcli annotation_specs reorder_labels \
     --project_id prj1 \
     --label_name_en bus car


ラベルIDを指定して並び替える
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs reorder_labels \
     --project_id prj1 \
     --label_id label_bus label_car


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.reorder_labels.add_parser
    :prog: annofabcli annotation_specs reorder_labels
    :nosubcommands:
    :nodefaultconst:
