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
    'comment' DOES NOT EQUAL ''
    'comment' MATCHES '[abc]+'
    'comment' MATCHES '[0-9]' IF 'unclear' EQUALS 'true'
    'type' EQUALS 'b690fa1a-7b3d-4181-95d8-f5c75927c3fc' IF 'unclear' EQUALS 'true'
    'link' HAS LABEL 'bike', 'bus'


``--format detaield_text`` を指定すると、属性IDなどの詳細情報も出力されます。

.. code-block::

    $ annofabcli annotation_specs list_attribute_restriction --project_id prj1 --format detailed_text
    'comment' (id='54fa5e97-6f88-49a4-aeb0-a91a15d11528', type='comment') DOES NOT EQUAL ''
    'comment' (id='54fa5e97-6f88-49a4-aeb0-a91a15d11528', type='comment') MATCHES '[abc]+'
    'comment' (id='54fa5e97-6f88-49a4-aeb0-a91a15d11528', type='comment') MATCHES '[0-9]' IF 'unclear' (id='f12a0b59-dfce-4241-bb87-4b2c0259fc6f', type='flag') EQUALS 'true'
    'type' (id='71620647-98cf-48ad-b43b-4af425a24f32', type='select') EQUALS 'b690fa1a-7b3d-4181-95d8-f5c75927c3fc'(name='medium') IF 'unclear' (id='f12a0b59-dfce-4241-bb87-4b2c0259fc6f', type='flag') EQUALS 'true'
    'link' (id='15235360-4f46-42ac-927d-0e046bf52ddd', type='link') HAS LABEL 'bike' (id='40f7796b-3722-4eed-9c0c-04a27f9165d2'), 'bus' (id='22b5189b-af7b-4d9c-83a5-b92f122170ec')



Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.list_attribute_restriction.add_parser
   :prog: annofabcli annotation_specs list_attribute_restriction
   :nosubcommands:
   :nodefaultconst:

