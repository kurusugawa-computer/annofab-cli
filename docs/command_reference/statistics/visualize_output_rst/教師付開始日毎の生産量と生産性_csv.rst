==========================================
教師付開始日毎の生産量と生産性.csv
==========================================

全体の生産量（作業したタスク数など）や生産性が、教師付開始日毎に記載されています。


`教師付開始日毎の生産量と生産性.csvのサンプル <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/statistics/visualize/out_dir/教師付開始日毎の生産量と生産性.csv>`_

列の内容
===================================================================================================



作業時間
----------
* ``worktime_hour`` : その日に教師付フェーズを開始して、現在作業が完了したタスクにかけた計測作業時間（アノテーションエディタ画面を触っていた作業の時間）。
* ``annotation_worktime_hour`` : 教師付フェーズの計測作業時間
* ``inspection_worktime_hour`` : 検査フェーズの計測作業時間
* ``acceptance_worktime_hour`` : 受入フェーズの計測作業時間

.. warning::

    ``worktime`` は、その日に教師付フェーズを開始したタスクにかかった作業時間です。その日に作業した時間ではないことに注意してください。


.. warning::

    ``--task_completion_criteria acceptance_reached`` を指定した場合、受入作業時間は0になります。
    受入フェーズに到達したタスクを「生産したタスク（作業が完了したタスク）」とする場合、受入作業時間は生産量に影響しないためです。




生産量
----------

* ``task_count`` : 作業が完了したタスクの数
* ``input_data_count`` : 作業が完了したタスクに含まれている入力データの数
* ``annotation_count`` : 作業が完了したタスクに含まれているアノテーションの数

``task_count`` の算出方法
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``--task_completion_criteria`` で指定した値によって、 ``task_count`` の算出方法が異なります。

``--task_completion_criteria acceptance_completed`` を指定すると、 ``task_count`` は、受入フェーズ完了状態のタスクの数になります。

``--task_completion_criteria acceptance_reached`` を指定すると、 ``task_count`` は、受入フェーズタスクの数になります。


生産性
----------

* ``worktime_hour/input_data_count`` : 入力データあたり計測作業時間
* ``worktime_hour/annotation_count`` : アノテーションあたり計測作業時間


その他
--------------------------


* ``first_annotation_started_date`` : 教師付フェーズを開始した日


