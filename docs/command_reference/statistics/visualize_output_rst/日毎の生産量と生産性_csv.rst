==========================================
日毎の生産量と生産性.csv
==========================================


全体の生産量（作業したタスク数など）や生産性が、日毎に記載されています。

`日毎の生産量と生産性.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/statistics/visualize/out_dir/日毎の生産量と生産性.csv>`_

参照頻度が高い列の詳細を、以下に記載します。

* monitored_worktime_hour: 計測作業時間[hour](アノテーションエディタ画面を触っていた作業時間）
* actual_worktime_hour: 実績作業時間[hour](労務管理画面から入力した作業時間）
* task_count: 作業したタスク数。タスクが初めて受入完了状態になったときに「作業した」とみなしている。
* input_data_count: 作業したタスクに含まれている入力データ数
* actual_worktime/annotation_count: アノテーションあたりの実績作業時間[hour]。生産性の指標になる。


.. info::

    task_count は「その日に初めて受入完了状態になったタスクの個数」です。受入完了状態のタスクが差し戻されても、task_countは変わりません。
    受入完了状態の差し戻し後の作業量が多い場合、task_countの値が実際と合わないケースがあります。
    
