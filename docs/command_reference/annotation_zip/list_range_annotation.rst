====================================================================================
annotation_zip list_range_annotation
====================================================================================


Description
=================================
アノテーションZIPから動画プロジェクトの区間アノテーションの情報を出力します。

動画プロジェクト以外のプロジェクトでは実行できません。


Examples
=================================

基本的な使用例
-------------------------------

.. code-block:: bash

    $ annofabcli annotation_zip list_range_annotation --project_id prj1 --output out.csv --format csv


.. code-block:: bash

    $ annofabcli annotation_zip list_range_annotation --annotation annotation.zip --output out.json --format pretty_json


出力結果の例（JSON形式）
-------------------------------

.. code-block:: json
    :caption: out.json

    [
      {
        "project_id": "proj1",
        "task_id": "task_00",
        "task_status": "complete",
        "task_phase": "annotation",
        "task_phase_stage": 1,
        "input_data_id": "input1",
        "input_data_name": "video1.mp4",
        "updated_datetime": "2023-10-01T12:00:00.000+09:00",
        "label": "音声",
        "annotation_id": "ann1",
        "begin_second": 10.5,
        "end_second": 15.8,
        "duration_second": 5.3,
        "attributes": {
          "speaker": "male",
          "language": "ja"
        }
      }
    ]


出力結果の例（CSV形式）
-------------------------------

.. csv-table::
   :header: project_id,task_id,task_status,task_phase,task_phase_stage,input_data_id,input_data_name,updated_datetime,label,annotation_id,begin_second,end_second,duration_second,attributes.speaker,attributes.language

    proj1,task_00,complete,annotation,1,input1,video1.mp4,2023-10-01T12:00:00.000+09:00,音声,ann1,10.5,15.8,5.3,male,ja


出力項目
=================================

CSV形式およびJSON形式で以下の項目が出力されます：

* ``project_id``: プロジェクトID
* ``task_id``: タスクID
* ``task_status``: タスクステータス
* ``task_phase``: タスクフェーズ
* ``task_phase_stage``: タスクフェーズの段階
* ``input_data_id``: 入力データID
* ``input_data_name``: 入力データ名
* ``updated_datetime``: アノテーションJSONの更新日時
* ``label``: アノテーションのラベル
* ``annotation_id``: アノテーションID
* ``begin_second``: 区間の開始時刻（秒）
* ``end_second``: 区間の終了時刻（秒）
* ``duration_second``: 区間の長さ（秒）
* ``attributes``: アノテーションの属性情報（JSON形式）
* ``attributes.{属性名}``: 各属性の値（CSV形式）


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_zip.list_range_annotation.add_parser
    :prog: annofabcli annotation_zip list_range_annotation
    :nosubcommands:
    :nodefaultconst:


