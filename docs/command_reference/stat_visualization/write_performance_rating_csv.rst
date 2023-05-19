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

生産性の指標は、 ``--productivity_indicator`` または ``--productivity_indicator_by_directory`` で指定できます。
品質の指標は、 ``--quality_indicator`` または ``--quality_indicator_by_directory`` で指定できます。



出力結果
=================================



.. code-block::

    $ annofabcli stat_visualization write_performance_rating_csv --dir out_dir --output_dir out_dir2/


.. code-block::

    out_dir2/
    ├── annotation_productivity
    │   ├── annotation_productivity__original.csv
    │   ├── annotation_productivity__deviation.csv
    │   ├── annotation_productivity__rank.csv
    │   └── annotation_productivity__summary.csv
    ├── annotation_quality
    │   ├── annotation_quality__original.csv
    │   ├── annotation_quality__deviation.csv
    │   ├── annotation_quality__rank.csv
    │   └── annotation_quality__summary.csv
    └── inspection_acceptance_
        ├── inspection_acceptance_productivity__original.csv
        ├── inspection_acceptance_productivity__deviation.csv
        ├── inspection_acceptance_productivity__rank.csv
        └── inspection_acceptance_productivity__summary.csv


* `annotation_productivity_rank.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/stat_visualization/write_performance_rating_csv/out/annotation_productivity_rank.csv>`_
* `annotation_productivity_deviation.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/stat_visualization/write_performance_rating_csv/out/annotation_productivity_deviation.csv>`_



``{評価対象}__{評価方法}.csv`` という名前のCSVファイルが出力されます。

* 評価対象
    * annotation_productivity: 教師付の生産性（単位あたり実績作業時間）
    * inspection_acceptance_productivity: 検査/受入の生産性（単位あたり実績作業時間）
    * annotation_quality: 教師付の品質（タスクあたり差し戻し回数）
    * annotation_quality_per_task: 教師付の品質（単位あたりの検査コメント数）
* 評価方法
    * original: 生産性または品質の値
    * deviation: 偏差値。値が小さいほど、生産性/品質が高い。
    * rank: 四分位数から算出したランキング。A,B,C,Dの順に生産性/品質が低くなる。
    * summary: プロジェクトごとに生産性または品質の値を平均値などで集約した結果

Usage Details
=================================

.. argparse::
   :ref: annofabcli.stat_visualization.write_performance_rating_csv.add_parser
   :prog: annofabcli stat_visualization write_performance_rating_csv
   :nosubcommands:
   :nodefaultconst:

See also
=================================
* `annofabcli statistics visualize <../statistics/visualize.html>`_
