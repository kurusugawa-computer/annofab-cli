====================================================================================
annotation_zip list_classification_annotation
====================================================================================


Description
=================================
アノテーションZIPから全体アノテーション（Classification）の情報を出力します。


Examples
=================================

基本的な使い方
--------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_classification_annotation --project_id prj1 --output out.json --format pretty_json



.. code-block:: json
    :caption: out.json

    [
      {
        "project_id": "proj1",
        "task_id": "task_00",
        "task_status": "complete",
        "task_phase": "annotation",
        "task_phase_stage": 1,
        "input_data_id": "i1",
        "input_data_name": "i1.jpg",
        "updated_datetime": "2023-10-01T12:00:00.000+09:00",
        "label": "climatic",
        "annotation_id": "ann1",
        "annotation_editor_url": "https://annofab.com/projects/proj1/tasks/task_00/editor?#i1/ann1",
        "attributes": {
          "weather": "sunny"
        }
      }
    ]


動画プロジェクトのアノテーションZIPを指定する
------------------------------------------------------------

``--annotation`` で動画プロジェクトのアノテーションZIPまたはディレクトリを指定する場合は、``--annotation_editor_type video`` を指定してください。

.. code-block:: bash

    $ annofabcli annotation_zip list_classification_annotation \
        --annotation annotation.zip \
        --annotation_editor_type video \
        --output out.csv


特定のラベルのみ出力
--------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_classification_annotation --project_id prj1 --label_name climatic quality --output out.csv



出力項目について
=================================

基本情報
--------------------

* ``project_id`` : プロジェクトID
* ``task_id`` : タスクID
* ``task_status`` : タスクのステータス（not_started, working, complete, など）
* ``task_phase`` : タスクのフェーズ（annotation, inspection, acceptance）
* ``task_phase_stage`` : タスクのフェーズステージ（1から始まる整数）
* ``input_data_id`` : 入力データID
* ``input_data_name`` : 入力データ名
* ``updated_datetime`` : アノテーションJSONの更新日時（ISO 8601形式）
* ``label`` : ラベル名
* ``annotation_id`` : アノテーションID
* ``annotation_editor_url`` : アノテーションエディタのURL。対象のアノテーションを直接開くことができます。

属性情報
--------------------

* ``attributes`` : 属性情報。JSON形式ではオブジェクト、CSV形式では ``attributes.属性名`` の形式で列が追加されます。


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_zip.list_classification_annotation.add_parser
    :prog: annofabcli annotation_zip list_classification_annotation
    :nosubcommands:
    :nodefaultconst:
