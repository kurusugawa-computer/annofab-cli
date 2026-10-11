==========================================
annotation_zip diff
==========================================

Description
=================================

2つのローカルのアノテーションZIPまたは展開ディレクトリを比較し、アノテーションの追加・削除・変更を出力します。
Annofabへのログインは不要です。Simple形式のアノテーションを使用してください。

Examples
=================================

.. code-block:: bash

    $ annofabcli annotation_zip diff \
        --left_annotation old.zip --right_annotation new.zip

.. code-block:: bash

    $ annofabcli annotation_zip diff \
        --left_annotation old/ --right_annotation new.zip \
        --format detail_text --output diff.txt

属性だけを比較する場合は ``--target attributes`` を指定します。
アノテーションの追加・削除は、指定したフィールドにかかわらず出力します。

比較ルール
=================================

* ``task_id`` はJSONの親ディレクトリ名、 ``input_data_id`` はJSONファイルの拡張子を除いた名前から取得します。
  この2つとJSON内の ``annotation_id`` の組み合わせで対応付けます。
* ``label`` 、 ``data`` 、 ``attributes`` を比較します。
  JSON内の ``project_id`` 、 ``task_id`` 、 ``input_data_id`` 、 ``updated_datetime`` 、タスクのステータス・フェーズ、入力データ名などの補足情報は比較しません。
* アノテーションの並び順と、属性を含むオブジェクトのキーの並び順は無視します。
  属性値の配列や座標配列は順序も比較します。座標に許容誤差は設けません。
* 属性キーの追加・削除・値の変更を区別します。キーの欠落と ``null`` 、空文字列は異なる値です。
  真偽値と数値（例： ``true`` と ``1`` ）は区別します。数値の ``1`` と ``1.0`` は同じ値として扱います。
* ディレクトリ名・JSONファイル名・ ``annotation_id`` の変更は削除と追加になります。
* 外部ファイルの参照パスだけの変更は差分にしません。参照されていないファイルは比較しません。
* ``Unknown`` 型のdataに埋め込まれた3DのJSONは、文字列の整形やキーの順序を無視して比較します。

外部ファイルの比較
---------------------------------

塗りつぶし画像（ ``Segmentation`` / ``SegmentationV2`` ）は次の順に比較します。

1. ファイルサイズが異なる場合は、PNGをデコードして真偽値のマスクを比較します。
2. ファイルサイズが同じ場合は、バイト列を比較します。一致すれば差分なしです。
3. バイト列が異なる場合は、PNGをデコードしてマスクを比較します。

マスクの縦横サイズが異なれば差分ありです。同じ場合は全画素の塗りつぶし状態を比較します。
圧縮設定やPNGのメタデータだけが異なる場合は差分になりません。

3Dセグメントは、 ``kind: SEGMENT`` 、 ``version: "1"`` （またはversion省略）の外部JSONを読み込み、
``points`` に含まれる点インデックスの集合を比較します。並び順は無視します。
左右の入力点群で点インデックスが対応していることを前提とします。元の点群の座標は比較しません。
点インデックスの一覧は出力せず、詳細出力には左右の点数と、右側で追加・削除された点数を出力します。

比較に必要な外部ファイルの欠落・読み込み時の破損・未対応形式はエラーになります。
バイト列が一致した塗りつぶし画像はデコードしないため、画像形式の検証も省略します。
``--target`` に ``data`` を含めない場合は外部ファイルを読み込みません。
追加・削除されたアノテーションはIDのみを出力し、その外部ファイルの内容は検証しません。

出力結果
=================================

``--format`` は ``annotation_specs diff`` と同じ4形式です。CSV出力には対応していません。

* ``text`` : 変更項目・属性キーを階層形式で表示します。既定の形式です。
* ``detail_text`` : 変更前後の値と、外部ファイルの差分件数も表示します。
* ``json`` / ``pretty_json`` : 変更フラグ・属性キー・外部ファイルの差分件数をJSONで出力します。
  変更前後の値は ``detail_text`` で確認してください。

``added`` は右側にのみ存在、 ``removed`` は左側にのみ存在、 ``changed`` は両側に存在して結果が異なるアノテーションです。

``text`` の例です。

.. code-block:: yaml

    [annotations]
    changed:
    - task_id: task1
      input_data_id: image1
      annotation_id: anno1
      fields:
      - data
      - attributes
      data_changed: true
      attributes_changed: true
      external_file_changed: true
      added_attribute_keys: []
      removed_attribute_keys: []
      changed_attribute_keys:
      - occluded

``detail_text`` の3Dセグメントの例です。

.. code-block:: yaml

    [annotations]
    changed:
    - task_id: task1
      input_data_id: pointcloud1
      annotation_id: anno1
      fields:
      - data
      data_changed: true
      external_file_changed: true
      external_file:
        kind: SEGMENT
        point_count:
          left: 3
          right: 3
        added_point_count: 1
        removed_point_count: 1

塗りつぶし画像の詳細出力は、左右の画像サイズ（幅・高さ）、左右の塗りつぶし画素数と変更画素数を含みます。
画像サイズが異なる場合、変更画素数は ``null`` です。

JSON出力の例です。

.. code-block:: bash

    $ annofabcli annotation_zip diff \
        --left_annotation old.zip --right_annotation new.zip \
        --format pretty_json --output diff.json

.. code-block:: json

    {
      "annotations": {
        "added": [],
        "removed": [],
        "changed": [
          {
            "task_id": "task1",
            "input_data_id": "image1",
            "annotation_id": "anno1",
            "label_changed": false,
            "data_changed": false,
            "attributes_changed": true,
            "external_file_changed": false,
            "added_attribute_keys": [],
            "removed_attribute_keys": [],
            "changed_attribute_keys": ["occluded"]
          }
        ]
      },
      "has_diff": true
    }

差分がない場合、テキストは空になり、ログに「差分はありません。」と表示します。
JSONは ``has_diff: false`` と空の差分一覧を出力します。
比較が正常に完了した場合は差分の有無によらず終了コード0、比較エラーは非ゼロで終了します。

Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_zip.diff_annotation.add_parser
   :prog: annofabcli annotation_zip diff
   :nosubcommands:
   :nodefaultconst:
