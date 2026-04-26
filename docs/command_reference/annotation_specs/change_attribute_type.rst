==========================================
annotation_specs change_attribute_type
==========================================

Description
=================================
既存属性の種類を変更します。

現在対応している変換は、以下の組み合わせのみです。

* ``choice`` ↔ ``select``
* ``text`` ↔ ``comment``


Examples
=================================

ドロップダウンをラジオボタンへ変更する場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs change_attribute_type \
     --project_id prj1 \
     --attribute_name_en type \
     --attribute_type choice


自由記述（複数行）を自由記述（1行）へ変更する場合
--------------------------------------------------------------------------------------------

.. code-block::

    $ annofabcli annotation_specs change_attribute_type \
     --project_id prj1 \
     --attribute_id 54fa5e97-6f88-49a4-aeb0-a91a15d11528 \
     --attribute_type text


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.change_attribute_type.add_parser
    :prog: annofabcli annotation_specs change_attribute_type
    :nosubcommands:
    :nodefaultconst:
