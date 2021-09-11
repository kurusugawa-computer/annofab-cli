====================================================================================
stat_visualization write_performance_scatter_per_user
====================================================================================

Description
=================================
``annofabcli statistics visualize`` コマンドの出力ファイル ``メンバごとの生産性と品質.csv`` から、ユーザごとにプロットした散布図を出力します。


Examples
=================================

基本的な使い方
--------------------------

``--csv`` に ``annofabcli statistics visualize`` コマンドの出力ファイル ``メンバごとの生産性と品質.csv`` のパスを指定してください。


.. code-block::

    $ annofabcli statistics visualize --project_id prj1 --output_dir prj1_dir/

    $ annofabcli stat_visualization merge_peformance_per_date --csv prj1_dir/メンバごとの生産性と品質.csv \
     --output_dir scatter/



出力結果
=================================

.. code-block::

    $ annofabcli stat_visualization write_performance_scatter_per_user --csv prj1_dir/メンバごとの生産性と品質.csv \
     --output_dir scatter/

    $ ls -1 scatter/
    散布図-アノテーションあたり作業時間と品質の関係-実績時間-教師付者用.html
    散布図-アノテーションあたり作業時間と累計作業時間の関係-計測時間.html
    散布図-アノテーションあたり作業時間と累計作業時間の関係-実績時間.html
    散布図-教師付者の品質と作業量の関係.html


.. argparse::
   :ref: annofabcli.stat_visualization.write_performance_scatter_per_user.add_parser
   :prog: annofabcli stat_visualization write_performance_scatter_per_user
   :nosubcommands:


See also
=================================
* `annofabcli statistics visualize <../statistics/visualize.html>`_

