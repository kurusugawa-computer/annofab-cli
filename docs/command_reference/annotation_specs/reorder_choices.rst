==========================================
annotation_specs reorder_choices
==========================================

Description
=================================
アノテーション仕様の選択肢系属性（ラジオボタン/ドロップダウン）内の選択肢を並び替えます。

対象属性を1件指定します。
指定した選択肢を指定順で先頭に移動します。
指定しなかった選択肢は現在の順番を維持します。


Examples
=================================

属性名と選択肢名を指定して並び替える
----------------------------------------------

以下のコマンドは、"type" 属性に含まれる "small", "large" 選択肢をこの順番で先頭に移動します。
その他の選択肢は現在の順番を維持して、"small", "large" の後ろに並びます。

.. code-block::

    $ annofabcli annotation_specs reorder_choices \
     --project_id prj1 \
     --attribute_name_en type \
     --choice_name_en small large


属性IDと選択肢IDを指定して並び替える
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs reorder_choices \
     --project_id prj1 \
     --attribute_id attribute_type \
     --choice_id choice_small choice_large


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.reorder_choices.add_parser
    :prog: annofabcli annotation_specs reorder_choices
    :nosubcommands:
    :nodefaultconst:
