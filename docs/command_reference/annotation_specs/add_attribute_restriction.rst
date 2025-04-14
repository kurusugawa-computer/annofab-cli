==========================================
annotation_specs add_attribute_restriction
==========================================

Description
=================================
アノテーション仕様に属性の制約を追加します。
アノテーション仕様画面では設定できない「属性間の制約」を追加するときに有用です。


Examples
=================================


.. code-block:: json
    :caption: restrictions.json
    
    [
        {
            "additional_data_definition_id": "y",
            "condition": {
                "premise": {
                    "additional_data_definition_id": "x",
                    "condition": {
                        "value": "true",
                        "_type": "Equals"
                    }
                },
                "condition": {
                    "value": "",
                    "_type": "NotEquals"
                },
                "_type": "Imply"
            }
        }
    ]
    
    
.. code-block::

    $ annofabcli annotation_specs add_attribute_restriction --project_id prj1 --json file://restriction.json


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
