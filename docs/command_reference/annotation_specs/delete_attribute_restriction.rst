==========================================
annotation_specs delete_attribute_restriction
==========================================

Description
=================================
アノテーション仕様の属性制約を削除します。

``--json`` を指定すると、指定した属性制約のJSONと完全一致する制約を削除します。
``--attribute_id`` または ``--attribute_name_en`` を指定すると、指定した属性に紐づく属性制約をすべて削除します。

削除前には、削除対象の属性制約を ``list_attribute_restriction`` と同様のテキストで確認できます。


Examples
=================================

JSONで指定した属性制約を削除する
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs delete_attribute_restriction \
     --project_id prj1 \
     --json file://restrictions.json


属性名(英語)に紐づく属性制約をすべて削除する
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs delete_attribute_restriction \
     --project_id prj1 \
     --attribute_name_en comment


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.delete_attribute_restriction.add_parser
    :prog: annofabcli annotation_specs delete_attribute_restriction
    :nosubcommands:
    :nodefaultconst:


See also
=================================
*  `annofabcli annotation_specs list_attribute_restriction <../annotation_specs/list_attribute_restriction.html>`_
