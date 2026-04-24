==========================================
annotation_specs add_existing_attribute
==========================================

Description
=================================
アノテーション仕様に既に存在する属性を、既存ラベルへ追加します。
属性定義自体は新規作成せず、指定したラベルの ``additional_data_definitions`` に既存属性を追加します。


Examples
=================================

属性IDで指定する場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_existing_attribute \
     --project_id prj1 \
     --label_name_en car \
     --attribute_id attr1 attr2


属性名(英語)で指定する場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_existing_attribute \
     --project_id prj1 \
     --label_id label1 \
     --attribute_name_en weather color


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_existing_attribute.add_parser
    :prog: annofabcli annotation_specs add_existing_attribute
    :nosubcommands:
    :nodefaultconst:
