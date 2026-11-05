====================================================================================
annotation_specs delete_attribute_restriction
====================================================================================

Description
=================================
指定した属性に紐づくアノテーション仕様の属性制約を削除します。
``--attribute_id`` または ``--attribute_name_en`` が必須です。

制約を個別指定する場合は、:doc:`delete_attribute_restriction_per_restriction` を使用してください。
従来の ``--restriction_json`` は、そのコマンドに移動しました。




Examples
=================================

属性名(英語)に紐づく属性制約をすべて削除する
----------------------------------------------

``--attribute_id`` または ``--attribute_name_en`` を指定すると、指定した属性に紐づく属性制約をすべて削除します。

.. code-block::

    $ annofabcli annotation_specs delete_attribute_restriction \
     --project_id prj1 \
     --attribute_name_en comment


属性名(英語)に紐づく相関制約だけを削除する
----------------------------------------------

``--restriction_type`` を指定すると、対象属性に紐づく制約のうち、指定した種類の制約だけを削除できます。

.. code-block::

    $ annofabcli annotation_specs delete_attribute_restriction \
     --project_id prj1 \
     --attribute_name_en comment \
     --restriction_type imply


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.delete_attribute_restriction.create_parser
    :prog: annofabcli annotation_specs delete_attribute_restriction
    :nosubcommands:
    :nodefaultconst:


See also
=================================
*  `annofabcli annotation_specs list_attribute_restriction <../annotation_specs/list_attribute_restriction.html>`_
