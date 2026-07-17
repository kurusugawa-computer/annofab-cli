==========================================
annotation_specs add_attributes
==========================================

Description
=================================
アノテーション仕様に複数の属性を追加します。選択肢系属性（ラジオボタン/ドロップダウン）もJSONでまとめて指定できます。

1件の選択肢系属性を追加し、選択肢情報をCSVで指定したい場合は :doc:`add_choice_attribute` を使用してください。


Examples
=================================

JSON形式で指定する場合
----------------------------------------------

.. code-block:: json
    :caption: attributes.json

    [
        {
            "attribute_type": "flag",
            "attribute_name_en": "unclear",
            "read_only": true,
            "default_value": false,
            "keybind": {
                "alt": false,
                "code": "Digit1",
                "ctrl": true,
                "shift": false
            },
            "label_name_ens": ["car", "bus"]
        },
        {
            "attribute_type": "select",
            "attribute_name_en": "weather",
            "choices": [
                {
                    "choice_name_en": "sunny",
                    "choice_name_ja": "晴れ",
                    "is_default": true,
                    "keybind": {
                        "alt": false,
                        "code": "Digit2",
                        "ctrl": true,
                        "shift": false
                    }
                },
                {
                    "choice_name_en": "cloudy",
                    "choice_name_ja": "曇り"
                }
            ],
            "label_name_ens": ["bike"]
        }
    ]

.. code-block::

    $ annofabcli annotation_specs add_attributes \
     --project_id prj1 \
     --attribute_json file://attributes.json


--attribute_json の構造
=================================

``--attribute_json`` には、属性情報のJSON配列を指定します。各要素は1件の属性を表すJSONオブジェクトです。

各属性オブジェクトでは、以下のキーを指定できます。

* ``attribute_type`` : 必須。属性の種類。指定できる値は :ref:`annotation_specs_non_choice_attribute_types` を参照してください。
* ``attribute_name_en`` : 必須。属性名（英語）。
* ``label_name_ens`` : ``label_ids`` とどちらか一方が必須。属性を追加する対象ラベルの英語名一覧。
* ``label_ids`` : ``label_name_ens`` とどちらか一方が必須。属性を追加する対象ラベルの ``label_id`` 一覧。
* ``attribute_name_ja`` : 任意。属性名（日本語）。
* ``attribute_id`` : 任意。属性ID。未指定の場合はUUIDv4が自動生成されます。
* ``read_only`` : 任意。 ``true`` を指定すると読み込み専用の属性として追加します。未指定の場合は ``false`` です。
* ``default_value`` : 任意。非選択肢系属性の初期値。 ``attribute_type`` が ``flag`` の場合は真偽値、 ``integer`` の場合は整数、その他の場合は文字列を指定します。 ``choice`` または ``select`` では指定できません。
* ``keybind`` : 任意。属性に設定するキーボードショートカット。JSONオブジェクトを指定してください。
* ``choices`` : ``attribute_type`` が ``choice`` または ``select`` のとき必須。選択肢情報の配列です。各要素では、以下のキーを指定できます。

  * ``choice_name_en`` : 必須。選択肢名（英語）。
  * ``choice_name_ja`` : 任意。選択肢名（日本語）。
  * ``choice_id`` : 任意。選択肢ID。未指定の場合はUUIDv4が自動生成されます。
  * ``is_default`` : 任意。 ``true`` を指定すると属性の初期値として使用します。未指定の場合は ``false`` です。
  * ``keybind`` : 任意。選択肢に設定するキーボードショートカット。JSONオブジェクトを指定してください。

``attribute_type`` には、非選択肢系属性の値に加えて ``choice`` と ``select`` も指定できます。


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_attributes.add_parser
    :prog: annofabcli annotation_specs add_attributes
    :nosubcommands:
    :nodefaultconst:
