==========================================
annotation_specs add_labels
==========================================

Description
=================================
アノテーション仕様にラベルを複数件追加します。
追加するラベルの ``annotation_type`` は共通です。


Examples
=================================

ラベル名(英語)を複数指定する場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_labels \
     --project_id prj1 \
     --label_name_en pedestrian bicycle traffic_light \
     --annotation_type bounding_box


ファイルからラベル名(英語)一覧を読み込む場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs add_labels \
     --project_id prj1 \
     --label_name_en file://label_names.txt \
     --annotation_type segmentation_v2


Usage Details
=================================

``--annotation_type`` の値
----------------------------------------------

.. list-table::
    :header-rows: 1

    * - 値
      - 説明
      - 使用できるプロジェクト
    * - ``bounding_box``
      - 矩形
      - 画像プロジェクト
    * - ``segmentation``
      - 塗りつぶし（インスタンスセグメンテーション用）
      - 画像プロジェクト
    * - ``segmentation_v2``
      - 塗りつぶしv2（セマンティックセグメンテーション用）
      - 画像プロジェクト
    * - ``polygon``
      - ポリゴン（閉じた頂点集合）
      - 画像プロジェクト
    * - ``polyline``
      - ポリライン（開いた頂点集合）
      - 画像プロジェクト
    * - ``point``
      - 点
      - 画像プロジェクト
    * - ``classification``
      - 全体分類
      - 画像プロジェクト、動画プロジェクト
    * - ``range``
      - 動画の区間
      - 動画プロジェクト
    * - ``custom``
      - カスタム
      - カスタムプロジェクト
    * - ``user_bounding_box``
      - 3次元のバウンディングボックス
      - 3次元プロジェクト
    * - ``user_instance_segment``
      - 3次元のインスタンスセグメント
      - 3次元プロジェクト
    * - ``user_semantic_segment``
      - 3次元のセマンティックセグメント
      - 3次元プロジェクト

.. argparse::
    :ref: annofabcli.annotation_specs.add_labels.add_parser
    :prog: annofabcli annotation_specs add_labels
    :nosubcommands:
    :nodefaultconst:
