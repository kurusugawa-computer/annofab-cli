==========================================
annotation_specs delete_labels
==========================================

Description
=================================
アノテーション仕様からラベルを削除します。

削除対象ラベルだけが参照している属性も削除します。
また、削除対象ラベルまたは削除される属性に関連する属性制約も削除します。

削除対象ラベルが既存アノテーションで使われている場合は、デフォルトでは削除できません。
既存アノテーションに影響することを理解した上でラベルを削除する場合は、 ``--allow_affecting_annotations`` を指定してください。


Examples
=================================

ラベル名を指定して削除する
----------------------------------------------

以下のコマンドは、"car", "bus" ラベルを削除します。

.. code-block::

    $ annofabcli annotation_specs delete_labels \
     --project_id prj1 \
     --label_name_en car bus


ラベルIDを指定して削除する
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs delete_labels \
     --project_id prj1 \
     --label_id label1 label2


既存アノテーションに影響する変更を許可する
------------------------------------------------------------

.. code-block::

    $ annofabcli annotation_specs delete_labels \
     --project_id prj1 \
     --label_name_en car bus \
     --allow_affecting_annotations


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.delete_labels.add_parser
    :prog: annofabcli annotation_specs delete_labels
    :nosubcommands:
    :nodefaultconst:
