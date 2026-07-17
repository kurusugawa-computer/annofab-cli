==========================================
annotation_specs add_choices_to_attribute
==========================================

Description
=================================
既存の選択肢系属性（ラジオボタン/ドロップダウン）に、選択肢を追加します。


Examples
=================================

JSON形式で指定する場合
----------------------------------------------

.. code-block:: json
    :caption: choices.json

    [
        {
            "choice_name_en": "xlarge"
        },
        {
            "choice_id": "c2",
            "choice_name_en": "tiny",
            "choice_name_ja": "極小",
            "keybind": {
                "alt": false,
                "code": "Digit1",
                "ctrl": true,
                "shift": false
            }
        }
    ]


.. code-block::

    $ annofabcli annotation_specs add_choices_to_attribute \
     --project_id prj1 \
     --attribute_name_en type \
     --choice_json file://choices.json


CSV形式で指定する場合
----------------------------------------------

.. code-block::
    :caption: choices.csv

    choice_id,choice_name_en,choice_name_ja,keybind
    ,xlarge,,
    c2,tiny,極小,"{""alt"": false, ""code"": ""Digit1"", ""ctrl"": true, ""shift"": false}"


.. code-block::

    $ annofabcli annotation_specs add_choices_to_attribute \
     --project_id prj1 \
     --attribute_id 71620647-98cf-48ad-b43b-4af425a24f32 \
     --choice_csv choices.csv

選択肢の ``keybind`` を指定する場合は、 ``--choice_json`` ではJSONオブジェクト、 ``--choice_csv`` ではJSONオブジェクト文字列を指定してください。APIの ``keybind`` は配列形式ですが、このコマンドでは画面と同じく1つだけ指定できます。


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_choices_to_attribute.add_parser
    :prog: annofabcli annotation_specs add_choices_to_attribute
    :nosubcommands:
    :nodefaultconst:
