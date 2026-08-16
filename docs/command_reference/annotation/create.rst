====================================================================================
annotation create
====================================================================================

Description
=================================
各アノテーションを新規作成します。既存アノテーションは更新または削除しません。
入力の ``annotation_id`` が既存アノテーションと一致する場合、そのアノテーションは作成せずにスキップします。
外部ファイルが必要な塗りつぶしアノテーションなどは、このコマンドではサポートしていません。

Examples
=================================

JSON形式で指定する
---------------------------------------

``--json`` に、作成するアノテーションの情報をJSON形式で指定します。

.. code-block:: json
    :caption: annotations.json

    [
        {
            "task_id": "t1",
            "input_data_id": "i1",
            "annotation_id": "new-car-001",
            "label": "car",
            "data": {
                "_type": "BoundingBox",
                "left_top": {"x": 100, "y": 200},
                "right_bottom": {"x": 300, "y": 400}
            },
            "attributes": {"occluded": false},
            "editor_props": {"can_delete": false}
        }
    ]

.. code-block:: console

    $ annofabcli annotation create --project_id p1 --json file://annotations.json --backup backup_dir/

``annotation_id`` は任意です。省略した場合は新しいIDを自動で採番します。同じ入力を再実行したときの重複を避けるには、安定した ``annotation_id`` を指定してください。

CSV形式で指定する
---------------------------------------

``--csv`` にはヘッダ行付きのCSVファイルを指定します。

.. csv-table::
   :header: 列名,必須,備考

    task_id,Yes,
    input_data_id,Yes,
    label,Yes,ラベル名（英語）
    data,Yes,アノテーションdata（JSON形式）
    annotation_id,No,
    attributes,No,属性名と値のオブジェクト（JSON形式）
    editor_props,No,エディタ用プロパティのオブジェクト（JSON形式）

``editor_props`` をまとめて指定する
---------------------------------------

``--editor_props`` を指定すると、作成するすべてのアノテーションに同じエディタ用プロパティを付与します。入力JSONまたはCSVの ``editor_props`` に同じキーを指定した場合は、その値が優先されます。

.. code-block:: console

    $ annofabcli annotation create --project_id p1 --json file://annotations.json \
      --editor_props '{"can_delete": false}' --backup backup_dir/

バックアップ
---------------------------------------

``--backup`` に実行前のアノテーション情報を保存するディレクトリを指定できます。作成したアノテーションを取り消すには、 `annotation restore <../annotation/restore.html>`_ コマンドを使用してください。

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.create_annotation.add_parser
    :prog: annofabcli annotation create
    :nosubcommands:
    :nodefaultconst:
