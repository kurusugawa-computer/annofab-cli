==========================================
annotation_specs change_attribute_type
==========================================

Description
=================================
既存属性の種類を変更します。

現在対応している変換は、以下の組み合わせのみです。

* ``choice`` （ラジオボタン） ↔ ``select`` （ドロップダウン）

.. warning::
    
    変更対象の属性を参照しているアノテーションがすでに存在する場合は、注意してください。
    
    * 3次元エディタ画面：属性の種類を変更すると、対象属性の値は消えます。
    * 画像エディタ画面/動画エディタ画面：2026年4月時点では、属性の種類を変更しても、対象属性の値は消えません。保持されます。
    


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
