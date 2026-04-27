==========================================
annotation_specs unset_attribute_required
==========================================

Description
=================================
属性の必須制約を解除します。


Examples
=================================


.. code-block::

    $ annofabcli annotation_specs unset_attribute_required \
     --project_id prj1 \
     --attribute_id attr1 attr2 attr3



Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.unset_attribute_required.add_parser
    :prog: annofabcli annotation_specs unset_attribute_required
    :nosubcommands:
    :nodefaultconst:
