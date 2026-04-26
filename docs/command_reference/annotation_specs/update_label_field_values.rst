==========================================
annotation_specs update_label_field_values
==========================================

Description
=================================
アノテーション仕様の既存ラベルに設定された ``field_values`` を、マージ・置換・クリアのいずれかで更新します。
``field_values`` にはサイズ制約や許容誤差範囲などの情報を設定できます。


Examples
=================================

既存の ``field_values`` にマージする場合
----------------------------------------------

.. code-block:: json
    :caption: field_values.json

	{
        // 矩形のサイズ制約（幅また高さが20px以上）
		"minimum_size_2d_with_default_insert_position": {
			"min_warn_rule": {
				"_type": "Or"
			},
			"min_width": 20,
			"min_height": 20,
			"position_for_minimum_bounding_box_insertion": null,
			"_type": "MinimumSize2dWithDefaultInsertPosition"
		}
	}


.. note::

    ``field_values`` のフォーマットは、 `getAnnotationSpecs API<https://annofab.com/docs/api/#tag/af-annotation-specs/operation/getAnnotationSpecs>`_ の
    レスポンス（ ``AnnotationSpecsV3`` ）配下の ``field_values`` を参照してください。

    なお、 ``annofabcli annotation_specs list_label`` コマンドで、ラベルの ``field_values`` を確認できます。
    
    




.. code-block::

    $ annofabcli annotation_specs update_label_field_values \
     --project_id prj1 \
     --label_name_en car bus \
     --field_values_json file://field_values.json


``field_values`` 全体を置換する場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs update_label_field_values \
     --project_id prj1 \
     --label_name_en car \
     --field_values_json file://field_values.json \
     --replace


``field_values`` をクリアする場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs update_label_field_values \
     --project_id prj1 \
     --label_id label1 label2 \
     --clear








Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.update_label_field_values.add_parser
    :prog: annofabcli annotation_specs update_label_field_values
    :nosubcommands:
    :nodefaultconst:
