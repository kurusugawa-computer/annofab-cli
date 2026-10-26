==========================================
annotation_specs add_attribute
==========================================

Description
=================================
アノテーション仕様に非選択肢系の属性を追加します。


Examples
=================================

以下のコマンドは、"car", "bus"ラベルにチェックボックス属性を追加します。

.. code-block::

    $ annofabcli annotation_specs add_attribute \
     --project_id prj1 \
     --attribute_type flag \
     --attribute_name_en unclear \
     --attribute_name_vi "không rõ" \
     --label_name_en car bus

読み込み専用属性にする
----------------------------------------------
読み込み専用の属性を追加する場合は、 ``--read_only`` を指定します。

.. code-block::

    $ annofabcli annotation_specs add_attribute \
     --project_id prj1 \
     --attribute_type text \
     --attribute_name_en external_id \
     --read_only \
     --label_name_en car

属性の初期値を設定する
----------------------------------------------
初期値を指定する場合は、 ``--default_value`` を指定します。

.. code-block::

    $ annofabcli annotation_specs add_attribute \
     --project_id prj1 \
     --attribute_type text \
     --attribute_name_en memo \
     --default_value "確認済み" \
     --label_name_en car

``--attribute_type`` が ``flag`` の場合、 ``--default_value`` には ``true`` または ``false`` を指定します。 ``integer`` の場合は整数を指定します。


ショートカットキーを設定する
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_attribute \
     --project_id prj1 \
     --attribute_type flag \
     --attribute_name_en unclear \
     --keybind_json '{"alt": false, "code": "Digit1", "ctrl": true, "shift": false}' \
     --label_name_en car

``--keybind_json`` にはJSONオブジェクトを指定してください。
``code`` に指定できる値は、 `KeyboardEvent.code <https://developer.mozilla.org/ja/docs/Web/API/KeyboardEvent/code>`_ を参照してください。

.. _annotation_specs_non_choice_attribute_types:

--attribute_type に指定できる値
=================================

``--attribute_type`` には、 :ref:`annotation_specs_attribute_types` のうち、 ``choice`` と ``select`` を除く非選択肢系属性を指定できます。

追加位置の指定
=================================

``--before_attribute_name_en`` に既存属性の英語名を指定すると、その属性の直前に追加します。
未指定の場合は末尾に追加します。
属性定義全体の一覧と各対象ラベルの属性一覧の両方に適用します。
既存属性同士の相対的な順序は維持します。

基準属性は、コマンド実行前から存在し、属性定義全体で英語名が一意である必要があります。
全対象ラベルに基準属性が含まれている必要があり、1つでも含まれない場合は更新全体をエラーにします。
基準属性が存在しない場合や英語名が重複する場合も、アノテーション仕様は更新しません。

.. code-block::

    $ annofabcli annotation_specs add_attribute \
     --project_id prj1 \
     --attribute_type flag \
     --attribute_name_en new_flag \
     --label_name_en car bike \
     --before_attribute_name_en unclear


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_attribute.add_parser
    :prog: annofabcli annotation_specs add_attribute
    :nosubcommands:
    :nodefaultconst:
