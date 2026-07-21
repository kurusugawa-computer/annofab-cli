==========================================
annotation_specs delete_choices
==========================================

Description
=================================
アノテーション仕様の選択肢系属性（ラジオボタン/ドロップダウン）から選択肢を削除します。

削除対象選択肢に関連する属性制約も削除します。

削除後の選択肢数が2件未満になる場合は削除できません。
削除対象選択肢が属性のデフォルト値に設定されている場合は、デフォルトでは削除できません。
デフォルト値を解除した上で選択肢を削除する場合は、 ``--unsafe_defaults`` を指定してください。

削除対象選択肢が既存アノテーションで使われている場合は、デフォルトでは削除できません。
既存アノテーションに影響することを理解した上で選択肢を削除する場合は、 ``--allow_affecting_annotations`` を指定してください。


Examples
=================================

選択肢名を指定して削除する
----------------------------------------------

以下のコマンドは、"type" 属性から "large", "medium" 選択肢を削除します。

.. code-block::

    $ annofabcli annotation_specs delete_choices \
     --project_id prj1 \
     --attribute_name_en type \
     --choice_name_en large medium


選択肢IDを指定して削除する
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs delete_choices \
     --project_id prj1 \
     --attribute_id 71620647-98cf-48ad-b43b-4af425a24f32 \
     --choice_id choice_large choice_medium


デフォルト値に設定されている選択肢を削除する
------------------------------------------------------------

``--unsafe_defaults`` を指定すると、削除対象選択肢が属性のデフォルト値に設定されていても、デフォルト値を解除して選択肢を削除します。

.. code-block::

    $ annofabcli annotation_specs delete_choices \
     --project_id prj1 \
     --attribute_name_en type \
     --choice_name_en large \
     --unsafe_defaults


既存アノテーションに影響する変更を許可する
------------------------------------------------------------

.. code-block::

    $ annofabcli annotation_specs delete_choices \
     --project_id prj1 \
     --attribute_name_en type \
     --choice_name_en large \
     --allow_affecting_annotations


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.delete_choices.add_parser
    :prog: annofabcli annotation_specs delete_choices
    :nosubcommands:
    :nodefaultconst:
