==========================================
annotation_specs add_choices_to_attributes
==========================================

Description
=================================
既存の複数選択肢系属性（ラジオボタン/ドロップダウン）に、選択肢を追加します。

複数属性への選択肢追加を1回のアノテーション仕様更新として実行できます。
1つの属性にだけ選択肢を追加したい場合は :doc:`add_choices_to_attribute` も利用できます。

``attribute_id`` 、既存選択肢、選択肢の並び順、属性の ``default_value`` は変更できません。
属性の ``default_value`` を変更したい場合は :doc:`update_attributes` を利用してください。


Examples
=================================

JSON形式で指定する場合
----------------------------------------------

.. code-block:: json
    :caption: attributes.json

    [
        {
            "attribute_id": "71620647-98cf-48ad-b43b-4af425a24f32",
            "choices": [
                {
                    "choice_id": "xlarge",
                    "choice_name_en": "xlarge",
                    "choice_name_ja": "特大",
                    "choice_name_vi": "rất lớn"
                },
                {
                    "choice_id": "tiny",
                    "choice_name_en": "tiny",
                    "choice_name_ja": "極小"
                }
            ]
        },
        {
            "attribute_id": "e6d5bf13-9bf5-4c31-8a81-2d8a772c9468",
            "choices": [
                {
                    "choice_name_en": "rainy",
                    "choice_name_ja": "雨",
                    "keybind": {
                        "alt": false,
                        "code": "Digit1",
                        "ctrl": true,
                        "shift": false
                    }
                }
            ]
        }
    ]


.. code-block::

    $ annofabcli annotation_specs add_choices_to_attributes \
     --project_id prj1 \
     --attribute_json file://attributes.json


``--attribute_json`` には、選択肢追加情報のJSON配列を指定してください。配列の各要素が1件の属性に対応します。

.. list-table::
    :header-rows: 1

    * - キー
      - 必須
      - 説明
    * - ``attribute_id``
      - 必須
      - 選択肢を追加する対象属性の ``attribute_id`` 。
    * - ``choices``
      - 必須
      - 追加する選択肢情報の配列。1件以上指定してください。

``choices`` には、追加する選択肢情報を指定してください。配列の各要素が1件の選択肢に対応します。

.. list-table::
    :header-rows: 1

    * - キー
      - 必須
      - 説明
    * - ``choice_name_en``
      - 必須
      - 追加する選択肢の英語名。
    * - ``choice_id``
      - 任意
      - 追加する選択肢の ``choice_id`` 。未指定の場合はUUIDv4が自動生成されます。
    * - ``choice_name_ja``
      - 任意
      - 追加する選択肢の日本語名。
    * - ``choice_name_vi``
      - 任意
      - 追加する選択肢のベトナム語名。
    * - ``keybind``
      - 任意
      - キーボードショートカットのJSONオブジェクト。 ``code`` に指定できる値は、 `KeyboardEvent.code <https://developer.mozilla.org/ja/docs/Web/API/KeyboardEvent/code>`_ を参照してください。
    * - ``is_default``
      - 任意
      - 指定されても無視されます。デフォルト値を変更したい場合は :doc:`update_attributes` を利用してください。


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.add_choices_to_attributes.add_parser
    :prog: annofabcli annotation_specs add_choices_to_attributes
    :nosubcommands:
    :nodefaultconst:
