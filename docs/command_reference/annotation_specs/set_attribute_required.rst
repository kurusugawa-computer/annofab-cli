==========================================
annotation_specs set_attribute_required
==========================================

Description
=================================
属性の必須制約を設定します。

Examples
=================================


.. code-block::

    $ annofabcli annotation_specs set_attribute_required \
     --project_id prj1 \
     --attribute_name_en color size note



Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.set_attribute_required.add_parser
    :prog: annofabcli annotation_specs set_attribute_required
    :nosubcommands:
    :nodefaultconst:
