====================================================================================
annotation_specs add_existing_attribute_to_labels
====================================================================================

Description
=================================
アノテーション仕様に既に存在する属性1個を、複数の既存ラベルへ追加します。
属性定義自体は新たに作成しません。

Examples
=================================

属性名(英語)とlabel_idで指定する場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_existing_attribute_to_labels \
     --project_id prj1 \
     --attribute_name_en weather \
     --label_id label1 label2


属性IDとラベル名(英語)で指定する場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_existing_attribute_to_labels \
     --project_id prj1 \
     --attribute_id attr1 \
     --label_name_en car bus


追加位置の指定
=================================

``--before_attribute_name_en`` で、各対象ラベル内の既存属性の直前に追加できます。
未指定の場合は末尾に追加します。基準属性の条件は :doc:`add_attribute` と同じです。
このコマンドは属性定義を作成せず、属性定義全体の並び順も変更しません。


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_existing_attribute_to_labels.add_parser
    :prog: annofabcli annotation_specs add_existing_attribute_to_labels
    :nosubcommands:
    :nodefaultconst:
