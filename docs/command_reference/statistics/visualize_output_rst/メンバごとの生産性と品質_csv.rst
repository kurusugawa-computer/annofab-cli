==========================================
メンバごとの生産性と品質.csv
==========================================

メンバごとの生産量（作業したタスク数など）や生産性、教師付の品質が分かります。

`メンバごとの生産性と品質.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/statistics/visualize/out_dir/メンバごとの生産性と品質.csv>`_

参照頻度が高い列の詳細を、以下に記載します。

* monitored_worktime_hour: 計測作業時間[hour](アノテーションエディタ画面を触っていた作業時間）
* actual_worktime_hour: 実績作業時間[hour](労務管理画面から入力した作業時間）
* task_count: 作業したタスク数
* input_data_count: 作業したタスクに含まれている入力データ数
* actual_worktime_hour/annotation_count: アノテーションあたりの実績作業時間[hour]。生産性の指標になる。
* pointed_out_inspection_comment_count/annotation_count: アノテーションあたりの指摘を受けた個数（対応完了状態の検査コメント）。品質の指標になる。
* rejected_count/task_count: タスクあたりの差し戻された回数。品質の指標になる。


.. note::

    タスクの教師付を複数人で作業した場合、ユーザごとにmonitored_worktime_hourで按分した値を「作業した」とみなします。
    たとえば、task1の教師付の作業にユーザAが45分、ユーザBが15かかっとします。その場合、「ユーザAはtask1を0.75、ユーザBはtask1を0.25作業した」とみなします。
    したがって、task_countは小数になる場合があります。



.. note::

    品質の指標は以下の2つです。

    * pointed_out_inspection_comment_count/annotation_count
    * rejected_count/task_count

    ``rejected_count/task_count`` より ``pointed_out_inspection_comment_count/annotation_count`` の方が粒度が細かいので、 通常のプロジェクトでは  ``pointed_out_inspection_comment_count/annotation_count`` の方が良い指標になります。
    

