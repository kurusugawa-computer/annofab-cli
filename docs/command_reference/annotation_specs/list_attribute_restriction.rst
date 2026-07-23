====================================================================================
annotation_specs list_attribute_restriction
====================================================================================

Description
=================================
アノテーション仕様の属性の制約情報を出力します。




Examples
=================================

基本的な使い方
--------------------------

属性の制約を自然言語で出力します。

.. code-block::

    $ annofabcli annotation_specs list_attribute_restriction --project_id prj1
    'comment' is read-only
    'comment' is not empty
    'comment' matches '[abc]+'
    If 'unclear' is checked, 'comment' matches '[0-9]'.
    'type' is 'medium'
    'link' has labels 'bike', 'bus'


``--format json`` または ``--format pretty_json`` を指定すると、属性制約のJSONを出力できます。
このJSONはAPIのrestrictionオブジェクトそのものなので、将来的に削除コマンドなどへそのまま渡しやすい形式です。

.. code-block::

    $ annofabcli annotation_specs list_attribute_restriction --project_id prj1 --format pretty_json
    [
      {
        "additional_data_definition_id": "54fa5e97-6f88-49a4-aeb0-a91a15d11528",
        "condition": {
          "enable": false,
          "_type": "CanInput"
        }
      }
    ]


属性名(英語)に紐づく特定種類の制約だけを出力する
--------------------------------------------------------------------------------------------

``--restriction_type`` を指定すると、対象属性に紐づく属性制約のうち、指定した種類の制約だけを出力できます。
属性は ``--attribute_id`` または ``--attribute_name_en`` で指定できます。

.. code-block::

    $ annofabcli annotation_specs list_attribute_restriction \
     --project_id prj1 \
     --attribute_name_en comment \
     --restriction_type imply
    If 'unclear' is checked, 'comment' matches '[0-9]'.

.. code-block::

    $ annofabcli annotation_specs list_attribute_restriction \
     --project_id prj1 \
     --attribute_id 54fa5e97-6f88-49a4-aeb0-a91a15d11528 \
     --restriction_type imply



Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.list_attribute_restriction.add_parser
   :prog: annofabcli annotation_specs list_attribute_restriction
   :nosubcommands:
   :nodefaultconst:
