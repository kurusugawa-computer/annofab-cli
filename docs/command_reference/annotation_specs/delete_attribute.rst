==========================================
annotation_specs delete_attribute
==========================================

Description
=================================
アノテーション仕様のラベルから属性を削除します。

削除対象属性を含むラベルが既存アノテーションで使われている場合は、デフォルトでは削除できません。
既存アノテーションに影響することを理解した上で属性を削除する場合は、 ``--allow_affecting_annotations`` を指定してください。


Examples
=================================

指定したラベルから属性を削除する
----------------------------------------------

以下のコマンドは、"car", "bus"ラベルから "occluded" 属性を削除します。

.. code-block::

    $ annofabcli annotation_specs delete_attribute \
     --project_id prj1 \
     --attribute_name_en occluded \
     --label_name_en car bus


すべてのラベルから属性を削除する
----------------------------------------------

以下のコマンドは、"occluded" 属性が紐づいているすべてのラベルから、"occluded" 属性を削除します。

.. code-block::

    $ annofabcli annotation_specs delete_attribute \
     --project_id prj1 \
     --attribute_name_en occluded \
     --all_labels


既存アノテーションに影響する変更を許可する
------------------------------------------------------------

.. code-block::

    $ annofabcli annotation_specs delete_attribute \
     --project_id prj1 \
     --attribute_name_en occluded \
     --label_name_en car bus \
     --allow_affecting_annotations


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.delete_attribute.add_parser
    :prog: annofabcli annotation_specs delete_attribute
    :nosubcommands:
    :nodefaultconst:
