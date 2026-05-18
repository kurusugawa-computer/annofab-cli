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


* ``text`` : 差分項目のみを表示します。
* ``detail_text`` : 差分項目と変更前後の値を表示します。
* ``json`` : 差分情報をJSONで出力します。
* ``pretty_json`` : 差分情報を整形JSONで出力します。
* ``--target`` : 出力対象の差分を指定します。指定しない場合は ``labels`` と ``attributes`` の両方を出力します。


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.diff_annotation_specs.add_parser
   :prog: annofabcli annotation_specs diff
   :nosubcommands:
   :nodefaultconst:
