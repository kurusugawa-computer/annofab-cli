==========================================
日毎の生産量と生産性.csv
==========================================


全体の生産量（作業したタスク数など）や生産性が、日毎に記載されています。

`日毎の生産量と生産性.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/statistics/visualize/out_dir/日毎の生産量と生産性.csv>`_



* ``actual_worktime_hour`` : 実績作業時間（ ``--labor_csv`` で渡された実際の作業時間）。単位は時間。
* ``monitored_worktime_hour`` : 計測作業時間（アノテーションエディタ画面を触っていた作業の時間）。単位は時間。
* ``task_count`` : 作業が完了したタスクの数
* ``input_data_count`` : 作業が完了したタスクに含まれている入力データの数
* ``annotation_count`` : 作業が完了したタスクに含まれているアノテーションの数
* ``actual_worktime_hour/annotation_count`` : アノテーションあたりの実績作業時間。単位は時間。
* ``working_user_count`` : 作業したユーザーの数


``task_count`` の算出方法
=================================
``--task_completion_criteria`` で指定した値によって、 ``task_count`` の算出方法が異なります。

``--task_completion_criteria acceptance_completed`` を指定すると、 ``task_count`` は、初めて受入フェーズ完了状態になったタスクの数になります。
受入取消によって完了状態でないタスクも、「作業が完了したタスク」に含まれます。

``--task_completion_criteria acceptance_reached`` を指定すると、 ``task_count`` は、初めて受入フェーズになったタスクの数になります。
受入フェーズでの差し戻しによって受入フェーズでないタスクも、「作業が完了したタスク」に含まれます。



.. note:: 

     
    以下のタスクが多いと、 ``task_count`` の推移は実際よりも早い日にタスクが完了したように見えます。
    
    * 受入取消されたタスク（ ``--task_completion_criteria acceptance_completed`` の場合）
    * 受入フェーズで差し戻されたタスク（ ``--task_completion_criteria acceptance_reached`` の場合）
    
    その場合は :doc:`教師付開始日毎の生産量と生産性_csv` も参照することをお勧めします。
    :doc:`教師付開始日毎の生産量と生産性_csv` の ``task_count`` は、教師付フェーズを開始した日ごとに集計しています。
    一度に大量のタスクの教師付けフェーズを開始する運用でなければ、 :doc:`教師付開始日毎の生産量と生産性_csv` の方が生産量の推移を正しく表しているかもしれません。
    
    