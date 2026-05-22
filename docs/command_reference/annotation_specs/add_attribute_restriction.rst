==========================================
annotation_specs add_attribute_restriction
==========================================

Description
=================================
アノテーション仕様に属性の制約を追加します。
アノテーション仕様画面では設定できない「属性間の制約」を追加するときに有用です。


Examples
=================================
以下のコマンドは、「IDが"X"の属性の値が"true"のとき、IDが"Y"の属性は空文字ではない」という制約を追加します。

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

    $ annofabcli annotation_specs add_attribute_restriction --project_id prj1 --restriction_json file://restriction.json



属性制約のJSON形式については https://annofab.readme.io/docs/constraints-between-attributes を参照してください。

なお `annofabcli-llm annotation_specs parse_attribute_restriction <https://annofab-cli-llm.readthedocs.io/ja/latest/command_reference/parse_attribute_restriction.html>`_ コマンドを利用すると、自然言語で記載された制約から属性制約のJSONを生成できます。


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
