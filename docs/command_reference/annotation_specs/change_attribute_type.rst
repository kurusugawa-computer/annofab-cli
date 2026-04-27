==========================================
annotation_specs change_attribute_type
==========================================

Description
=================================
既存属性の種類を変更します。

現在対応している変換は、以下の組み合わせのみです。

* ``choice`` ↔ ``select``

実行前の確認メッセージでは、対象属性値を設定している既存アノテーションが存在するかどうかを確認します。3次元エディタでは属性種類の変更により属性値が消えてしまう恐れがあるため、既存アノテーションで使われている場合は注意して実行してください。


Examples
=================================

ドロップダウンをラジオボタンへ変更する場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs change_attribute_type \
     --project_id prj1 \
     --attribute_name_en type \
     --attribute_type choice

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.change_attribute_type.add_parser
    :prog: annofabcli annotation_specs change_attribute_type
    :nosubcommands:
    :nodefaultconst:
