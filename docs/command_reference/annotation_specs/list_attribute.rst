==========================================
annotation_specs list_attribute
==========================================

Description
=================================
アノテーション仕様の属性情報を出力します。




Examples
=================================

.. code-block::

    $ annofabcli annotation_specs list_attribute --project_id prj1 --output out.csv


出力結果
=================================



JSON出力
----------------------------------------------


.. code-block::

    $ annofabcli annotation_specs list_attribute --project_id prj1  --format pretty_json --output out.json



.. code-block::
    :caption: out.json


    [
    {
        "attribute_id": "0f739b17-c22b-4f4a-a791-d142eb0bcd41",
        "attribute_name_en": "truncation",
        "attribute_name_ja": "truncation",
        "attribute_name_vi": "truncation",
        "type": "flag",
        "default": false,
        "read_only": false,
        "choice_count": 0,
        "restriction_count": 0,
        "reference_label_count": 2,
        "keybind": "Ctrl+Digit1"
    },
    {
        "attribute_id": "a0f7c8ed-38dc-41e6-a18c-29a36d3e28f2",
        "attribute_name_en": "direction",
        "attribute_name_ja": "車の向き",
        "attribute_name_vi": "direction",
        "type": "select",
        "default": "f98a9545-5864-4e5b-a945-d327001a0179",
        "read_only": false,
        "choice_count": 6,
        "restriction_count": 1,
        "reference_label_count": 2,
        "keybind": ""
    }
    ]


* ``attribute_id`` : 属性ID。WebAPIの ``additional_data_definition_id`` または ``definition_id`` に対応しています。
* ``attribute_name_en`` : 属性名（英語）。
* ``attribute_name_ja`` : 属性名（日本語）。
* ``attribute_name_vi`` : 属性名（ベトナム語）。
* ``attribute_type`` : 属性の種類。WebAPIの ``AdditionalDataDefinitionType`` に対応しています。 ``type`` の値は以下のいずれかです。

  * ``flag`` : チェックボックス
  * ``integer`` : 整数
  * ``text`` : 自由記述（1行）
  * ``comment`` : 自由記述（複数行）
  * ``choice`` : ラジオボタン（排他選択）
  * ``select`` : ドロップダウン（排他選択）
  * ``tracking`` : トラッキングID
  * ``link`` : アノテーションリンク

* ``default`` : 属性の初期値。属性の種類がラジオボタンまたはドロップダウンの場合は、初期値として選択されている項目の ``choice_id`` です。
* ``read_only`` : 読み込み専用の属性か否か。
* ``choice_count`` : 選択肢の個数。ドロップダウン属性またはラジオボタン属性以外では0個です。
* ``restriction_count`` : 制約の個数。
* ``reference_label_count`` : 参照されているラベルの個数
* ``keybind`` : キーボードショートカット




Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.list_annotation_specs_attribute.add_parser
   :prog: annofabcli annotation_specs list_attribute
   :nosubcommands:
   :nodefaultconst:


