==========================================
annotation_specs update_choices
==========================================

Description
=================================
アノテーション仕様の既存選択肢に設定された日本語名、ショートカットキーを更新します。

``choice_id`` 、選択肢名(英語)、選択肢の並び順、属性の ``default_value`` は更新できません。
選択肢の並び順を変更したい場合は :doc:`reorder_choices` を、属性の ``default_value`` を変更したい場合は :doc:`update_attributes` を利用してください。


Examples
=================================

JSON形式で指定する場合
----------------------------------------------

.. code-block:: json
    :caption: choices.json

    [
        {
            "choice_name_en": "large",
            "choice_name_ja": "大",
            "keybind": {
                "alt": false,
                "code": "Digit1",
                "ctrl": true,
                "shift": false
            }
        },
        {
            "choice_id": "74691a87-7962-4fa9-ba52-7cc466ecd982",
            "keybind": null
        }
    ]


.. code-block::

    $ annofabcli annotation_specs update_choices \
     --project_id prj1 \
     --attribute_name_en type \
     --choice_json file://choices.json


``--choice_json`` には、選択肢更新情報のJSON配列を指定してください。配列の各要素が1件の選択肢に対応します。

.. list-table::
    :header-rows: 1

    * - キー
      - 必須
      - 説明
    * - ``choice_id``
      - 条件付き必須
      - 更新対象選択肢の ``choice_id`` 。 ``choice_name_en`` とどちらか一方を指定してください。
    * - ``choice_name_en``
      - 条件付き必須
      - 更新対象選択肢の英語名。 ``choice_id`` とどちらか一方を指定してください。この値自体は更新されません。
    * - ``choice_name_ja``
      - 任意
      - 更新後の選択肢日本語名。
    * - ``keybind``
      - 任意
      - 更新後のキーボードショートカットのJSONオブジェクト。 ``null`` を指定するとショートカットキーを解除します。 ``code`` に指定できる値は、 `KeyboardEvent.code <https://developer.mozilla.org/ja/docs/Web/API/KeyboardEvent/code>`_ を参照してください。


CSV形式で指定する場合
----------------------------------------------

.. code-block::
    :caption: choices.csv

    choice_id,choice_name_en,choice_name_ja,keybind
    ,large,大,"{""alt"": false, ""code"": ""Digit1"", ""ctrl"": true, ""shift"": false}"
    74691a87-7962-4fa9-ba52-7cc466ecd982,,小,


CSV形式では、 ``keybind`` 列だけはJSONオブジェクト文字列として指定してください。
そのため、CSVセル全体を ``"`` で囲み、JSON内の ``"`` は ``""`` のようにエスケープする必要があります。
``keybind`` 列が空欄の場合、ショートカットキーは変更されません。

.. code-block::

    $ annofabcli annotation_specs update_choices \
     --project_id prj1 \
     --attribute_id 71620647-98cf-48ad-b43b-4af425a24f32 \
     --choice_csv choices.csv


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.update_choices.add_parser
    :prog: annofabcli annotation_specs update_choices
    :nosubcommands:
    :nodefaultconst:
