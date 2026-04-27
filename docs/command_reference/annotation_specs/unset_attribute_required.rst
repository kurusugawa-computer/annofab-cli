==========================================
annotation_specs unset_attribute_required
==========================================

Description
=================================
属性の必須制約を解除します。
内部的には required の属性制約を削除します。


Examples
=================================

属性IDを指定して、複数属性の必須制約を解除する場合
--------------------------------------------------

.. code-block::

    $ annofabcli annotation_specs unset_attribute_required \
     --project_id prj1 \
     --attribute_id attr1 attr2 attr3


属性IDを記載したファイルを指定して、複数属性の必須制約を解除する場合
----------------------------------------------------------------

.. code-block::

    $ annofabcli annotation_specs unset_attribute_required \
     --project_id prj1 \
     --attribute_id file://attribute_ids.txt


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.unset_attribute_required.add_parser
    :prog: annofabcli annotation_specs unset_attribute_required
    :nosubcommands:
    :nodefaultconst:
