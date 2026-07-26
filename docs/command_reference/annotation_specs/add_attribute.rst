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

``--attribute_type`` には、以下の非選択肢系属性を指定できます。

* ``flag`` : チェックボックス
* ``integer`` : 整数
* ``text`` : 自由記述（1行）
* ``comment`` : 自由記述（複数行）
* ``tracking`` : トラッキングID
* ``link`` : アノテーションリンク

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_attribute.add_parser
    :prog: annofabcli annotation_specs add_attribute
    :nosubcommands:
    :nodefaultconst:
