====================================================================================
stat_visualization merge_peformance_csv_per_date
====================================================================================

Description
=================================
``annofabcli statistics visualize`` コマンドの出力ファイル ``日毎の生産量と生産性.csv`` をマージします。



Examples
=================================

基本的な使い方
--------------------------

``--csv`` に ``annofabcli statistics visualize`` コマンドの出力ファイル ``日毎の生産量と生産性.csv`` のパスを複数指定してください。



.. code-block::

    $ annofabcli statistics visualize --project_id prj1 --output_dir prj1_dir/
    $ annofabcli statistics visualize --project_id prj2 --output_dir prj2_dir/

    $ annofabcli stat_visualization merge_peformance_csv_per_date --csv prj1_dir/日毎の生産量と生産性.csv \
     prj2_dir/日毎の生産量と生産性.csv \
     --output merge_日毎の生産量と生産性.csv

Usage Details
=================================

.. argparse::
   :ref: annofabcli.stat_visualization.merge_peformance_per_date.add_parser
   :prog: annofabcli stat_visualization merge_peformance_csv_per_date
   :nosubcommands:

See also
=================================
* `annofabcli statistics visualize <../statistics/visualize.html>`_

