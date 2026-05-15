==========================================
annotation_specs delete_attribute_restriction
==========================================

Description
=================================
アノテーション仕様の属性制約を削除します。




Examples
=================================

JSONで指定した属性制約を削除する
----------------------------------------------

``--restriction_json`` を指定すると、指定した属性制約のJSONと完全一致する制約を削除します。

.. code-block::

    $ annofabcli annotation_specs delete_attribute_restriction \
     --project_id prj1 \
     --restriction_json file://restrictions.json


属性名(英語)に紐づく属性制約をすべて削除する
----------------------------------------------

``--attribute_id`` または ``--attribute_name_en`` を指定すると、指定した属性に紐づく属性制約をすべて削除します。

.. code-block::

    $ annofabcli annotation_specs delete_attribute_restriction \
     --project_id prj1 \
     --attribute_name_en comment


属性名(英語)に紐づく相関制約だけを削除する
----------------------------------------------

``--restriction_type`` を指定すると、対象属性に紐づく制約のうち、指定した種類の制約だけを削除できます。

.. code-block::

    $ annofabcli annotation_specs delete_attribute_restriction \
     --project_id prj1 \
     --attribute_name_en comment \
     --restriction_type imply


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
