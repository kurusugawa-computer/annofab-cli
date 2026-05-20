==========================================
annotation_specs diff
==========================================

Description
=================================
2つのアノテーション仕様を比較して、差分を出力します。


Examples
=================================

プロジェクト同士を比較する
---------------------------------

.. code-block::

    $ annofabcli annotation_specs diff \
      --left_project_id prj_a \
      --right_project_id prj_b


JSONファイル同士を比較する
---------------------------------

.. code-block::

    $ annofabcli annotation_specs diff \
      --left_annotation_specs_json old.json \
      --right_annotation_specs_json new.json \
      --format pretty_json \
      --output out.json


最新と過去のアノテーション仕様を比較する
------------------------------------------------

.. code-block::

    $ annofabcli annotation_specs diff \
      --left_project_id prj1 \
      --right_project_id prj1 \
      --right_before 3 \
      --format detail_text


出力結果
=================================

``--format`` オプションでは以下の出力形式を指定できます。

* ``text`` : 差分項目のみをセクション見出し付きの階層形式で表示します。セクション見出しは ``[labels]`` のような形式です。デフォルトの出力形式です。
* ``detail_text`` : 差分項目と比較元・比較先の値を、 ``changes`` 配下の ``left`` / ``right`` で表示します。セクション見出しは ``[labels]`` のような形式です。
* ``json`` : 差分情報をJSONで出力します。
* ``pretty_json`` : 差分情報を整形JSONで出力します。

``text`` 形式の出力例
---------------------------------

``text`` 形式では、差分の概要をセクション見出し付きの階層形式で表示します。

.. code-block::

    [labels]
    label_order_changed: true
    added:
    - pedestrian
    removed:
    - bicycle
    changed:
    - label_name_en: car
      fields:
      - label_name_ja
      - annotation_type
      - color
      - keybind
      - attributes
      - field_values
      - metadata
      added_attributes:
      - lane_no
      removed_attributes:
      - truncated

    [attributes]
    added:
    - lane_no
    removed:
    - truncated
    changed:
    - attribute_name_en: type
      fields:
      - choices
      - choices_order
      added_choices:
      - s
      - e
      removed_choices:
      - medium
      - small
      changed_choices:
      - choice_name_en: large
        fields:
        - choice_name_en

    [attribute_restrictions]
    changed:
    - attribute_name_en: lane_no
      added_restrictions:
      - '''lane_no'' is not empty'

    [inspection_phrases]
    added:
    - phrase_too_dark
    removed:
    - phrase_blur
    changed:
    - inspection_phrase_id: phrase_occluded
      fields:
      - inspection_phrase_name_ja

    [metadata]
    added:
    - added_key
    removed:
    - removed_key
    changed:
    - changed_key

``detail_text`` 形式の出力例
---------------------------------

``detail_text`` 形式では、変更された値を ``changes`` 配下の ``left`` / ``right`` で表示します。配列やオブジェクトは文字列として表示します。
ラベルの順序変更は ``text`` 形式と同じく、 ``label_order_changed: true`` と表示します。
``attribute_restrictions`` は ``text`` 形式と同じく、制約条件を文字列で表示します。
``metadata`` の追加・削除はキー名のみ表示します。

.. code-block::

    [labels]
    label_order_changed: true
    changed:
    - label_name_en: car
      changes:
        label_name_ja:
          left: 車
          right: 自動車
        annotation_type:
          left: bounding_box
          right: polygon
        color:
          left: '#FF0000'
          right: '#00FF00'
        keybind:
          left: ''
          right: Ctrl+Digit1
        attributes:
          left: '["type", "truncated"]'
          right: '["type", "lane_no"]'
        field_values:
          left: '{}'
          right: '{"score": 1}'
        metadata:
          left: '{}'
          right: '{"updated": true}'
      added_attributes:
      - lane_no
      removed_attributes:
      - truncated

    [attributes]
    changed:
    - attribute_name_en: type
      changes:
        choices:
          left: '["large2", "medium", "small", "special"]'
          right: '["large", "special", "s", "e"]'
        choices_order:
          left: '["large2", "medium", "small", "special"]'
          right: '["large", "special", "s", "e"]'
      added_choices:
      - s
      - e
      removed_choices:
      - medium
      - small
      changed_choices:
      - choice_name_en: large
        changes:
          choice_name_en:
            left: large2
            right: large

    [attribute_restrictions]
    changed:
    - attribute_name_en: lane_no
      added_restrictions:
      - '''lane_no'' is not empty'

    [inspection_phrases]
    changed:
    - inspection_phrase_id: phrase_occluded
      changes:
        inspection_phrase_name_ja:
          left: 隠れています
          right: 遮蔽されています

    [metadata]
    added:
    - added_key
    removed:
    - removed_key
    changed:
    - key: changed_key
      left: '{"version": 1}'
      right: '{"version": 2}'

JSON形式の出力
---------------------------------

JSON出力のトップレベルは以下の形式です。

.. code-block::
    :caption: out.json

    {
      "labels": {
        "label_order_changed": true,
        "added_label_ids": [],
        "removed_label_ids": [],
        "changed_labels": [
          {
            "label_id": "label_car",
            "color_changed": true,
            "keybind_changed": false,
            "label_name_ja_changed": true,
            "label_name_en_changed": false,
            "label_name_vi_changed": false,
            "attributes_order_changed": false,
            "added_attribute_ids": [],
            "removed_attribute_ids": [],
            "field_values_changed": false,
            "metadata_changed": false,
            "annotation_type_changed": false
          }
        ]
      },
      "attributes": {
        "added_attribute_ids": [],
        "removed_attribute_ids": [],
        "changed_attributes": [
          {
            "attribute_id": "attr_type",
            "type_changed": false,
            "keybind_changed": false,
            "default_changed": false,
            "read_only_changed": false,
            "attribute_name_ja_changed": false,
            "attribute_name_en_changed": false,
            "attribute_name_vi_changed": false,
            "metadata_changed": false,
            "choices_order_changed": true,
            "added_choice_ids": ["choice_s"],
            "removed_choice_ids": ["choice_small"],
            "changed_choices": []
          }
        ]
      },
      "attribute_restrictions": {
        "changed_attribute_restrictions": [
          {
            "attribute_id": "attr_lane_no",
            "added_restrictions": [
              {
                "condition": {
                  "_type": "NotEmpty"
                }
              }
            ],
            "removed_restrictions": []
          }
        ]
      },
      "inspection_phrases": {
        "added_inspection_phrase_ids": ["phrase_too_dark"],
        "removed_inspection_phrase_ids": ["phrase_blur"],
        "changed_inspection_phrases": [
          {
            "inspection_phrase_id": "phrase_occluded",
            "inspection_phrase_name_ja_changed": true,
            "inspection_phrase_name_en_changed": false,
            "inspection_phrase_name_vi_changed": false
          }
        ]
      },
      "metadata": {
        "added_metadata_keys": ["added_key"],
        "removed_metadata_keys": ["removed_key"],
        "changed_metadata_keys": ["changed_key"]
      }
    }


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.diff_annotation_specs.add_parser
   :prog: annofabcli annotation_specs diff
   :nosubcommands:
   :nodefaultconst:
