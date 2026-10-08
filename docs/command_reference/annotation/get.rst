==========================================
annotation get
==========================================

Description
=================================
指定した1個のタスクのアノテーションを、SimpleアノテーションZIPと同じディレクトリ構成・JSON形式で取得します。
プロジェクト全体のZIPを作成・ダウンロードせずに、現在保存されているアノテーションを取得できます。

JSONには ``getAnnotation`` APIのレスポンスを保存します。
塗りつぶし画像や3次元セグメントなどの外部ファイルがある場合は、``getEditorAnnotation`` APIでURLを取得してダウンロードします。
JSONと外部ファイルは別々のAPIで取得するため、実行中にアノテーションが更新されると内容が一致しない可能性があります。

プロジェクト全体のZIP取得には :doc:`download`、復元用データの取得には :doc:`dump` を使用してください。

Examples
=================================

.. code-block:: bash

    $ annofabcli annotation get --project_id prj1 --task_id task1 --output_dir annotations/

出力例は次のとおりです。

.. code-block:: text

    annotations/
    └── task1/
        ├── input1.json
        ├── input2.json
        └── input2/
            └── annotation1

``input2.json`` の例です。外部ファイルは ``input2/annotation1`` に保存します。
JSONのフォーマットについては https://annofab.com/docs/api/#tag/x-annotation-zip/Simple-Annotation-ZIP を参照してください。

.. code-block:: json

    {
      "project_id": "prj1",
      "annotation_format_version": "1.2.0",
      "task_id": "task1",
      "task_phase": "annotation",
      "task_phase_stage": 1,
      "task_status": "working",
      "input_data_id": "input2",
      "input_data_name": "image2.jpg",
      "details": [
        {
          "label": "road",
          "annotation_id": "annotation1",
          "data": {"_type": "SegmentationV2", "data_uri": "annotation1"},
          "attributes": {}
        }
      ]
    }

CSV出力には対応していません。
出力先に ``task1/`` が既に存在する場合はエラーになります。再取得する場合は別の出力先を指定してください。
取得に失敗した場合は処理を中断し、取得途中のタスクディレクトリを残しません。

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.get_annotation.add_parser
    :prog: annofabcli annotation get
    :nosubcommands:
    :nodefaultconst:
