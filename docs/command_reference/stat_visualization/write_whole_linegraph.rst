====================================================================================
stat_visualization write_whole_linegraph
====================================================================================

Description
=================================
``annofabcli statistics visualize`` コマンドの出力ファイル ``日毎の生産量と生産性.csv`` から、折れ線グラフを出力します。


Examples
=================================

基本的な使い方
--------------------------

``--csv`` に ``annofabcli statistics visualize`` コマンドの出力ファイル ``日毎の生産量と生産性.csv`` のパスを指定してください。



.. code-block::

    $ annofabcli statistics visualize --project_id prj1 --output_dir prj1_dir/
    
    $ annofabcli stat_visualization write_whole_linegraph --csv prj1_dir/日毎の生産量と生産性.csv \
     --output_dir line-graph/



出力結果
=================================

.. code-block::

    $ annofabcli stat_visualization write_whole_linegraph --csv prj1_dir/日毎の生産量と生産性.csv \
     --output_dir line-graph/

    $ ls -1 line-graph/
    折れ線-横軸_日-全体.html
    累積折れ線-横軸_日-全体.html


See also
=================================
* `annofabcli statistics visualize <../statistics/visualize.html>`_



