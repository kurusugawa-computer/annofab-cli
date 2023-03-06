====================================================================================
annotation_specs get_with_attribute_id_replaced_english_name
====================================================================================

Description
=================================
属性IDをUUIDから英語名に置換したアノテーション仕様のJSONを出力します。

アノテーション仕様は変更しません。画面のインポート機能を使って、アノテーション仕様を変更することを想定しています。

相関制約をJSONで直接設定する際などに利用すると便利です。IDをがUUID形式から分かりやすい名前になるため、JSON記述しやすくなります。

.. warning::

    既にアノテーションが存在する状態で属性IDを変更すると、既存のアノテーション情報が消える恐れがあります。十分注意して、属性IDを変更してください。



Examples
=================================

基本的な使い方
--------------------------


.. code-block::

    # 属性IDを英語名に変更したアノテーション仕様を出力
    $ annofabcli annotation_specs get_with_attribute_id_replaced_english_name --project_id prj1 --out out.json


特定の属性の属性IDのみ変更する場合は、 ``--attribute_name`` を指定してください。

.. code-block::

    $ annofabcli annotation_specs get_with_label_id_replaced_english_name --project_id prj1 \
     --attribute_name type  --out out.json




Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.get_annotation_specs_with_attribute_id_replaced.add_parser
   :prog: annofabcli annotation_specs get_with_label_id_replaced_english_name
   :nosubcommands:
   :nodefaultconst:

