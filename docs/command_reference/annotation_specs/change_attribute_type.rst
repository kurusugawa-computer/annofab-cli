==========================================
annotation_specs change_attribute_type
==========================================

Description
=================================
既存属性の種類を変更します。

対応している変換は、以下の組み合わせです。

* ``choice`` （ラジオボタン） ↔ ``select`` （ドロップダウン）
* ``text`` （自由記述複数行） ↔ ``comment`` （自由記述1行）
* ``text`` （自由記述複数行） ↔ ``integer`` （整数）
* ``comment`` （自由記述1行） → ``integer`` （整数）

このコマンドはアノテーション仕様だけを変更します。
既存アノテーションの属性値の型をそろえるには、変更後に :doc:`../annotation/normalize_attribute_type` を実行してください。
変換できない値の扱いも、同コマンドの説明を参照してください。

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
