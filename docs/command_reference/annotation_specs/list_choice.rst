==========================================
annotation_specs list_choice
==========================================

Description
=================================
アノテーション仕様のドロップダウンまたはラジオボタン属性の選択肢情報を出力します。

Examples
=================================

.. code-block::

    $ annofabcli annotation_specs list_choice --project_id prj1 --output out.csv



出力結果
=================================

JSON出力
----------------------------------------------
    
.. code-block::
    
    $ annofabcli annotation_specs list_choice --project_id prj1 --format pretty_json --output out.json


.. code-block::
    :caption: out.json

    [
    {
        "attribute_id": "a0f7c8ed-38dc-41e6-a18c-29a36d3e28f2",
        "attribute_name_en": "direction",
        "attribute_type": "select",
        "choice_id": "3475515f-ba44-4a8d-b32b-72635e420048",
        "choice_name_en": "rear",
        "choice_name_ja": "rear",
        "choice_name_vi": "rear",
        "is_default": false,
        "keybind": ""
    },
    {
        "attribute_id": "a0f7c8ed-38dc-41e6-a18c-29a36d3e28f2",
        "attribute_name_en": "direction",
        "attribute_type": "select",
        "choice_id": "a5ebf59b-0484-446d-ac11-14a4736026e4",
        "choice_name_en": "front",
        "choice_name_ja": "front",
        "choice_name_vi": "front",
        "is_default": false,
        "keybind": ""
    },    
    ]
    

* ``attribute_id`` : 属性ID
* ``attribute_name_en`` : 属性名（英語）
* ``attribute_type`` : 属性の種類
* ``choice_id`` : 選択肢ID
* ``choice_name_en`` : 選択肢名（英語）
* ``choice_name_ja`` : 選択肢名（日本語）
* ``choice_name_vi`` : 選択肢名（ベトナム語）
* ``is_default`` : 初期値として設定されているかどうか
* ``keybind`` : キーボードショートカット


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.list_annotation_specs_choice.add_parser
   :prog: annofabcli annotation_specs list_choice
   :nosubcommands:
   :nodefaultconst:
