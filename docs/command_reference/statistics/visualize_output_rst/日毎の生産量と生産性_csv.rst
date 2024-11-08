==========================================
日毎の生産量と生産性.csv
==========================================


全体の生産量（作業したタスク数など）や生産性が、日毎に記載されています。

`日毎の生産量と生産性.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/statistics/visualize/out_dir/日毎の生産量と生産性.csv>`_


列名だけでは内容が判断しづらい列名を、以下に記載します。

* ``actual_worktime_hour`` : 実績作業時間（ ``--labor_csv`` で渡された実際の作業時間）。単位は時間。
* ``monitored_worktime_hour`` : 計測作業時間（アノテーションエディタ画面を触っていた作業の時間）。単位は時間。
* ``task_count`` : 作業が完了したタスクの数
* ``input_data_count`` : 作業が完了したタスクに含まれている入力データの数
* ``annotation_count`` : 作業が完了したタスクに含まれているアノテーションの数
* ``actual_worktime_hour/annotation_count`` : アノテーションあたりの実績作業時間。単位は時間。
* ``working_user_count`` : 作業したユーザーの数


.. note:: 

    ``--task_completion_criteria`` で指定した値によって、 ``task_count`` の算出方法が異なります。
     
    ``--task_completion_criteria acceptance_completed`` を指定すると、 ``task_count`` は、その日に初めて受入フェーズ完了状態になったタスクの数になります。
    受入取消によって完了状態でないタスクも、「作業が完了したタスク」に含まれます。    なお、受入取消されたタスクが多いと、 ``task_count`` は生産量の推移を正しく表現できないときがあります。
    その場合は :doc:`教師付開始日毎の生産量と生産性_csv` の ``task_count`` 方が生産量の推移を正しく表現できているかもしれません。
    * ``--task_completion_criteria acceptance_reached`` : 「その日に初めて受入フェーズになったタスクの個数」です。受入フェーズで差し戻されたタスクも「作業が完了したタスク」に含まれます。
 


:doc:`.index`
:doc:`../index.rst`

:doc:`教師付開始日毎の生産量と生産性_csv.rst`

