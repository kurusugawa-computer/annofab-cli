==========================================
statistics list_video_duration
==========================================

Description
=================================

各タスクの動画の長さを出力します。



Examples
=================================


.. code-block::

    $ annofabcli statistics list_video_duration --project_id prj1




出力結果
=================================



CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli statistics list_video_duration  --project_id prj1 \
    --output out.csv --format csv


.. csv-table:: out.csv
    :header-rows: 1
    :file: list_video_duration/out.csv


JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli statistics list_video_duration  --project_id prj1 \
    --output out.json --format pretty_json



.. code-block::
    :caption: out.json

    [
    {
        "project_id": "project1",
        "task_id": "test1",
        "task_status": "complete",
        "task_phase": "acceptance",
        "task_phase_stage": 1,
        "input_data_id": "c37be9c2-c8e7-472b-8766-7f16e197c6ce",
        "input_data_name": "video1",
        "video_duration_second": 5.294,
        "input_data_updated_datetime": "2024-10-04T09:18:02.416+09:00"
    }
    ]



Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.list_video_duration.add_parser
   :prog: annofabcli statistics list_video_duration
   :nosubcommands:
   :nodefaultconst:
