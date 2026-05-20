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
---------------------------------

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
* ``detail_text`` : 差分項目と比較元・比較先の値を、 ``left`` / ``right`` を含む階層形式で表示します。セクション見出しは ``[labels]`` のような形式です。
* ``json`` : 差分情報をJSONで出力します。
* ``pretty_json`` : 差分情報を整形JSONで出力します。

``text`` 形式の出力例
---------------------------------

``text`` 形式では、差分の概要をセクション見出し付きの階層形式で表示します。

.. code-block::

    [attributes]
    changed:
    - attribute_name_en: type
      fields:
      - choices
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

``detail_text`` 形式の出力例
---------------------------------

``detail_text`` 形式では、変更前後の値を ``left`` / ``right`` で表示します。配列やオブジェクトは文字列として表示します。

.. code-block::

    [attributes]
    changed:
    - name: type
      choices:
        left: '["large2", "medium", "small", "special"]'
        right: '["large", "special", "s", "e"]'
      added_choices:
      - s
      - e
      removed_choices:
      - medium
      - small
      changed_choices:
      - name: large
        choice_name_en:
          left: large2
          right: large

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
            "attributes_changed": true,
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
        "attribute_order_changed": true,
        "added_attribute_ids": [],
        "removed_attribute_ids": [],
        "changed_attributes": []
      }
    }


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.diff_annotation_specs.add_parser
   :prog: annofabcli annotation_specs diff
   :nosubcommands:
   :nodefaultconst:
