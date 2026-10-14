====================================================================================
annotation_specs update_label_field_values
====================================================================================

Description
=================================
アノテーション仕様の既存ラベルに設定された ``field_values`` を、マージ・置換・クリアのいずれかで更新します。
``field_values`` にはサイズ制約や許容誤差範囲などの情報を設定できます。
アノテーションの種類ごとのサンプルは、 :ref:`annotation_specs_field_values_samples` を参照してください。


Examples
=================================

既存の ``field_values`` にマージする場合
----------------------------------------------

以下のJSONは、矩形の最小幅と最小高さを20pxに設定します。

.. code-block:: json
    :caption: field_values.json

	{
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

    ``field_values`` のフォーマットは、 `getAnnotationSpecs API <https://annofab.com/docs/api/#tag/af-annotation-specs/operation/getAnnotationSpecs>`_ の
    レスポンス（ ``AnnotationSpecsV3`` ）配下の ``field_values`` を参照してください。

    なお、 :doc:`list_label` コマンドの出力結果で、各ラベルの ``field_values`` を確認できます。
    
    




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








.. _annotation_specs_field_values_samples:

``field_values`` のサンプル
=================================

``--field_values_json`` には、以下のJSONオブジェクトを指定します。
必要な設定だけを残し、数値を変更して使用できます。 ``_type`` にはサンプルの値をそのまま指定してください。



矩形（ ``bounding_box`` ）
----------------------------------------------

最小幅を100px、最小高さを200px、許容誤差を5pxに設定します。

``min_warn_rule._type`` は、幅と高さに関して警告を出す条件です。

* ``Or`` : 幅が ``min_width`` 未満、または高さが ``min_height`` 未満の場合に警告します。「幅100px以上 AND 高さ200px以上」という制約に使用します。
* ``And`` : 幅が ``min_width`` 未満、かつ高さが ``min_height`` 未満の場合に警告します。「幅100px以上 OR 高さ200px以上」という制約に使用します。

.. code-block:: json
    :caption: field_values.json

    {
        "minimum_size_2d_with_default_insert_position": {
            "_type": "MinimumSize2dWithDefaultInsertPosition",
            "min_warn_rule": {
                "_type": "Or"
            },
            "min_width": 100,
            "min_height": 200
        },
        "margin_of_error_tolerance": {
            "_type": "MarginOfErrorTolerance",
            "max_pixel": 5
        }
    }


ポリゴン（ ``polygon`` ）
----------------------------------------------

最小幅と最小高さを20px、最小面積を400平方ピクセル、頂点数を3～10個、許容誤差を5pxに設定します。

.. code-block:: json
    :caption: field_values.json

    {
        "minimum_size_2d": {
            "_type": "MinimumSize2d",
            "min_warn_rule": {
                "_type": "Or"
            },
            "min_width": 20,
            "min_height": 20
        },
        "minimum_area_2d": {
            "_type": "MinimumArea2d",
            "min_area": 400
        },
        "margin_of_error_tolerance": {
            "_type": "MarginOfErrorTolerance",
            "max_pixel": 5
        },
        "vertex_count_min_max": {
            "_type": "VertexCountMinMax",
            "min": 3,
            "max": 10
        }
    }


ポリライン（ ``polyline`` ）
----------------------------------------------

幅100px以上または高さ200px以上の最小サイズ制約、頂点数2～20個、許容誤差5pxを設定し、線分の方向を表示します。
``display_line_direction.has_direction`` を ``false`` にすると、線分の方向を表示しません。
``vertex_count_min_max.min`` または ``max`` に ``null`` を指定すると、その側の頂点数制約を設定しません。

.. code-block:: json
    :caption: field_values.json

    {
        "minimum_size_2d": {
            "_type": "MinimumSize2d",
            "min_warn_rule": {
                "_type": "And"
            },
            "min_width": 100,
            "min_height": 200
        },
        "margin_of_error_tolerance": {
            "_type": "MarginOfErrorTolerance",
            "max_pixel": 5
        },
        "display_line_direction": {
            "_type": "DisplayLineDirection",
            "has_direction": true
        },
        "vertex_count_min_max": {
            "_type": "VertexCountMinMax",
            "min": 2,
            "max": 20
        }
    }


塗りつぶし・塗りつぶしv2（ ``segmentation`` ・ ``segmentation_v2`` ）
------------------------------------------------------------------------------------

最小幅と最小高さを20px、許容誤差を5pxに設定します。

.. code-block:: json
    :caption: field_values.json

    {
        "minimum_size_2d": {
            "_type": "MinimumSize2d",
            "min_warn_rule": {
                "_type": "Or"
            },
            "min_width": 20,
            "min_height": 20
        },
        "margin_of_error_tolerance": {
            "_type": "MarginOfErrorTolerance",
            "max_pixel": 5
        }
    }


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.update_label_field_values.add_parser
    :prog: annofabcli annotation_specs update_label_field_values
    :nosubcommands:
    :nodefaultconst:
