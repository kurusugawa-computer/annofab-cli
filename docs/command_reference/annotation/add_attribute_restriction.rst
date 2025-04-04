==========================================
annotation add_attribute_restriction
==========================================

Description
=================================
アノテーション仕様に属性の制約を追加します。
このコマンドは、指定されたプロジェクトに対して新しい属性制約を追加するために使用されます。

Examples
=================================

.. code-block::

    $ annofabcli annotation_specs add_attribute_restriction --project_id prj1 --json '[{"additional_data_definition_id": "a1", "condition": {"value": "true", "_type": "Equals"}}]'

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_attribute_restriction.add_parser
    :prog: annofabcli annotation_specs add_attribute_restriction
    :nosubcommands:
    :nodefaultconst:

See also
=================================
*  `annofabcli annotation_specs list_attribute_restriction <../annotation_specs/list_attribute_restriction.html>`_
