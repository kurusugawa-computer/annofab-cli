==========================================
annotation_specs update_label_field_values
==========================================

Description
=================================
既存ラベルの ``field_values`` を更新します。

既定動作では、指定したJSONオブジェクトを既存の ``field_values`` にマージします。
``--replace`` を指定すると ``field_values`` 全体を置換し、``--clear`` を指定すると空辞書に更新します。


Examples
=================================

既存の ``field_values`` にマージする場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs update_label_field_values \
     --project_id prj1 \
     --label_name_en car bus \
     --field_values_json '{"margin_of_error_tolerance":{"_type":"MarginOfErrorTolerance","max_pixel":3}}'


``field_values`` 全体を置換する場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs update_label_field_values \
     --project_id prj1 \
     --label_name_en car \
     --field_values_json '{"display_line_direction":{"_type":"DisplayLineDirection","value":true}}' \
     --replace


``field_values`` をクリアする場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs update_label_field_values \
     --project_id prj1 \
     --label_id label1 label2 \
     --clear


JSONファイルで指定する場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs update_label_field_values \
     --project_id prj1 \
     --label_name_en car \
     --field_values_json file://field_values.json


.. note::

    現在の ``field_values`` を確認したい場合は、 ``annofabcli annotation_specs list_label`` コマンドを利用してください。
    CSV出力の ``field_values`` 列にはJSON文字列が出力されます。


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.update_label_field_values.add_parser
    :prog: annofabcli annotation_specs update_label_field_values
    :nosubcommands:
    :nodefaultconst:
