====================================================================================
stat_visualization write_performance_rating_csv
====================================================================================

Description
=================================

プロジェクトごとユーザごとにパフォーマンスを評価できる複数のCSVを出力します。




Examples
=================================

基本的な使い方
--------------------------


.. code-block::

    $ annofabcli statistics visualize --project_id prj1 prj2 --output_dir out_dir/


.. code-block::

    out_dir/
    ├── prj1
    │   ├── タスクlist.csv
    │   ├── メンバごとの生産性と品質.csv
    │   └── ...
    ├── prj2
    │   ├── タスクlist.csv
    │   ├── メンバごとの生産性と品質.csv
    │   └── ...


.. code-block::

    $ annofabcli stat_visualization write_performance_rating_csv --dir out_dir --output_dir out_dir2/





出力結果
=================================



.. code-block::

    $ annofabcli stat_visualization write_performance_rating_csv --dir out_dir --output_dir out_dir2/


.. code-block::

    out_dir2/
    ├── annotation_productivity_deviation.csv
    ├── annotation_productivity_rank.csv
    ├── annotation_quality_per_annotation_deviation.csv
    ├── annotation_quality_per_annotation_rank.csv
    ├── annotation_quality_per_task_deviation.csv
    ├── annotation_quality_per_task_rank.csv
    ├── inspection_acceptance_productivity_deviation.csv
    ├── inspection_acceptance_productivity_rank.csv



* `annotation_productivity_rank.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/stat_visualization/write_performance_rating_csv/out/annotation_productivity_rank.csv>`_
* `annotation_productivity_deviation.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/stat_visualization/write_performance_rating_csv/out/annotation_productivity_deviation.csv>`_



``{評価対象}_{評価方法}.csv`` という名前のCSVファイルが出力されます。


* 評価対象
    * annotation_productivity: 教師付の生産性（アノテーションあたり実績作業時間）
    * inspection_acceptance_productivity: 検査/受入の生産性（アノテーションあたり実績作業時間）
    * annotation_quality_per_annotation: 品質（アノテーションあたりの検査コメント数）
    * annotation_quality_per_task: 品質（タスクあたりの検査コメント数）
* 評価方法
    * deviation: 偏差値。値が小さいほど、生産性/品質が高い。
    * rank: 四分位数から算出したランキング。A,B,C,Dの順に生産性/品質が低くなる。




See also
=================================
* `annofabcli statistics visualize <../statistics/visualize.html>`_
