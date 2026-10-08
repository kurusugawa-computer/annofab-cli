==========================================
annotation export
==========================================

Description
=================================
指定したタスクのアノテーションを、SimpleアノテーションZIPと同じディレクトリ構成・JSON形式で書き出します。
プロジェクト全体のZIPを作成・ダウンロードせずに、現在保存されているアノテーションを取得できます。

JSONには ``getAnnotation`` APIのレスポンスを保存します。
JSONは2スペースでインデントしたpretty形式で保存し、ファイル末尾に改行を付けます。
塗りつぶし画像や3次元セグメントなどの外部ファイルがある場合は、``getEditorAnnotation`` APIでURLを取得してダウンロードします。
JSONと外部ファイルは別々のAPIで取得するため、実行中にアノテーションが更新されると内容が一致しない可能性があります。

書き出したデータの取り込みには :doc:`import` を使用してください。
``import`` は状態を完全に復元する操作ではありません。
バックアップ・復元には :doc:`dump` / :doc:`restore`、プロジェクト全体のZIP取得には :doc:`download` を使用してください。

Examples
=================================

.. code-block:: bash

    $ annofabcli annotation export --project_id prj1 --task_id task1 --output_dir annotations/

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
取得に失敗したタスクについては、取得途中のタスクディレクトリを残しません。

複数タスクの取得
--------------------------

``--task_id`` には複数のタスクIDを指定できます。
``file://`` によるファイル指定は :doc:`../../user_guide/user_guide` を参照してください。
同じタスクIDを複数回指定した場合は、1回だけ取得します。

.. code-block:: bash

    $ annofabcli annotation export --project_id prj1 --task_id task1 task2 task3 --output_dir annotations/ --parallelism 3

``--parallelism`` を指定すると、タスク単位で並列に取得します。
指定しない場合は逐次処理します。各タスク内の入力データは逐次処理します。
外部ファイルも取得します。

.. code-block:: text

    annotations/
    ├── task1/
    │   └── input1.json
    ├── task2/
    │   ├── input2.json
    │   └── input2/
    │       └── annotation1
    └── task3/
        └── input3.json

一部のタスクの取得に失敗しても、他のタスクの取得は続行し、成功したタスクの出力は保持します。
全タスクの処理後に成功件数と失敗件数をログに出力し、1件以上の失敗があれば終了コード1で終了します。

Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation.export_annotation.add_parser
    :prog: annofabcli annotation export
    :nosubcommands:
    :nodefaultconst:
