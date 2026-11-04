====================================================================================
annotation_specs delete_attribute_restriction_per_restriction
====================================================================================

Description
=================================
JSONで個別指定したアノテーション仕様の属性制約を削除します。
指定したJSONと完全一致する制約だけを削除します。

属性に紐づく制約をまとめて削除する場合は、:doc:`delete_attribute_restriction` を使用してください。
従来の ``delete_attribute_restriction --restriction_json`` は、このコマンドに移動しました。

Examples
=================================

``--restriction_json`` に、削除する属性制約のJSON配列を指定してください。
``list_attribute_restriction --format json`` と同じ形式です。

.. code-block:: json
   :caption: restrictions.json

   [
     {
       "additional_data_definition_id": "a1",
       "condition": {"value": "true", "_type": "Equals"}
     }
   ]

.. code-block::

    $ annofabcli annotation_specs delete_attribute_restriction_per_restriction \
     --project_id prj1 \
     --restriction_json file://restrictions.json

削除前に、対象の制約をまとめて確認します。
``--comment`` でアノテーション仕様の変更コメントを指定できます。

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.delete_attribute_restriction_per_restriction.create_parser
    :prog: annofabcli annotation_specs delete_attribute_restriction_per_restriction
    :nosubcommands:
    :nodefaultconst:

See also
=================================
* :doc:`delete_attribute_restriction`
* :doc:`list_attribute_restriction`
