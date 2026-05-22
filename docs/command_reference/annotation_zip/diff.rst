====================================================================================
annotation_zip diff
====================================================================================


Description
=================================
2つのアノテーションZIP、またはzipを展開したディレクトリを比較して、アノテーションの追加、削除、変更を出力します。

``left_annotation`` は比較元、``right_annotation`` は比較先として扱います。
たとえば、プレアノテーションを ``left_annotation``、人が確認・修正したアノテーションを ``right_annotation`` に指定すると、人が追加・削除・変更したアノテーションを確認できます。


Examples
=================================

サマリをCSVで出力する
--------------------

.. code-block:: bash

    $ annofabcli annotation_zip diff \
        --left_annotation pre_annotation.zip \
        --right_annotation reviewed_annotation.zip \
        --annotation_type bounding_box \
        --format summary_csv \
        --output summary.csv


詳細をCSVで出力する
--------------------

.. code-block:: bash

    $ annofabcli annotation_zip diff \
        --left_annotation pre_annotation.zip \
        --right_annotation reviewed_annotation.zip \
        --annotation_type bounding_box \
        --format detail_csv \
        --output detail.csv


JSONで出力する
--------------------

JSON形式では ``--annotation_type`` を省略できます。

.. code-block:: bash

    $ annofabcli annotation_zip diff \
        --left_annotation pre_annotation.zip \
        --right_annotation reviewed_annotation.zip \
        --format pretty_json \
        --output diff.json


変更がないアノテーションも詳細に出力する
--------------------------------------------------

.. code-block:: bash

    $ annofabcli annotation_zip diff \
        --left_annotation pre_annotation.zip \
        --right_annotation reviewed_annotation.zip \
        --annotation_type bounding_box \
        --format detail_csv \
        --include_unchanged \
        --output detail.csv


出力項目について
=================================

差分種別
--------------------

``diff_type`` には以下の値が出力されます。

* ``added`` : ``right_annotation`` にだけ存在するアノテーション
* ``deleted`` : ``left_annotation`` にだけ存在するアノテーション
* ``changed`` : 両方に存在し、ラベル、属性、アノテーションデータのいずれかが異なるアノテーション
* ``unchanged`` : 両方に存在し、内容が同じアノテーション

詳細出力では、デフォルトで ``added``、``deleted``、``changed`` のみ出力します。
``--include_unchanged`` を指定すると ``unchanged`` も出力します。


サマリCSV
--------------------

* ``left_annotation_count`` : 比較元のアノテーション数
* ``right_annotation_count`` : 比較先のアノテーション数
* ``added_count`` : 追加されたアノテーション数
* ``deleted_count`` : 削除されたアノテーション数
* ``changed_count`` : 変更されたアノテーション数
* ``unchanged_count`` : 変更がないアノテーション数


詳細CSV
--------------------

共通列として以下を出力します。

* ``label_changed`` : ラベルが変更されたかどうか
* ``attributes_changed`` : 属性が変更されたかどうか
* ``data_changed`` : 座標や区間などのアノテーションデータが変更されたかどうか
* ``changed_attribute_keys`` : 変更された属性キーのJSON配列

``added``、``deleted`` の行では比較できないため、``label_changed``、``attributes_changed``、``data_changed``、``changed_attribute_keys`` は空欄です。

アノテーション種類ごとの列として、以下のような変更量を出力します。

* ``bounding_box`` : ``iou``、``center_distance``、``area_change_ratio``
* ``single_point`` : ``point_distance``、``x_diff``、``y_diff``
* ``polygon`` : ``iou``、``centroid_distance``、``area_change_ratio``、``point_count_diff``
* ``polyline`` : ``length_change_ratio``、``start_point_distance``、``end_point_distance``、``midpoint_distance``、``point_count_diff``
* ``range`` : ``begin_diff_second``、``end_diff_second``、``duration_change_ratio``、``overlap_ratio``
* ``3d_bounding_box`` : ``center_distance``、``size_change_ratio``、``rotation_diff``


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_zip.diff_annotation.add_parser
    :prog: annofabcli annotation_zip diff
    :nosubcommands:
    :nodefaultconst:
