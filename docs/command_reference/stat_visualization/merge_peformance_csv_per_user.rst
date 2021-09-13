====================================================================================
stat_visualization merge_peformance_csv_per_user
====================================================================================

Description
=================================
``annofabcli statistics visualize`` コマンドの出力ファイル ``メンバごとの生産性と品質.csv`` をマージします。


Examples
=================================

基本的な使い方
--------------------------

``--csv`` に ``annofabcli statistics visualize`` コマンドの出力ファイル ``メンバごとの生産性と品質.csv`` のパスを複数指定してください。



.. code-block::

    $ annofabcli statistics visualize --project_id prj1 --output_dir prj1_dir/
    $ annofabcli statistics visualize --project_id prj2 --output_dir prj2_dir/

    $ annofabcli stat_visualization merge_peformance_csv_per_user --csv prj1_dir/メンバごとの生産性と品質.csv \
     prj2_dir/メンバごとの生産性と品質.csv \
     --output merge_メンバごとの生産性と品質.csv

Usage Details
=================================

.. argparse::
   :ref: annofabcli.stat_visualization.merge_peformance_per_user.add_parser
   :prog: annofabcli stat_visualization merge_peformance_csv_per_user
   :nosubcommands:

See also
=================================
* `annofabcli statistics visualize <../statistics/visualize.html>`_

