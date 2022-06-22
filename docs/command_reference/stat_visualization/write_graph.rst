====================================================================================
stat_visualization write_graph
====================================================================================

Description
=================================
``annofabcli statistics visualize`` コマンドの出力結果であるプロジェクトディレクトリから、グラフを出力します。


Examples
=================================

基本的な使い方
--------------------------

``--dir`` に ``annofabcli statistics visualize`` コマンドの出力結果であるプロジェクトディレクトリを指定してください。



.. code-block::

    $ annofabcli statistics visualize --project_id prj1 --output_dir prj1_dir/ --output_only_text
    
    $ annofabcli stat_visualization write_graph --dir prj1_dir/ --output_dir out/

    $ tree out/
    out
    ├── histogram
    │   ├── ヒストグラム-作業時間.html
    │   └── ヒストグラム.html
    ├── line-graph
    │   ├── 教師付者用
    │   │   ├── 折れ線-横軸_教師付開始日-縦軸_アノテーション単位の指標-教師付者用.html
    │   │   ├── 折れ線-横軸_教師付開始日-縦軸_入力データ単位の指標-教師付者用.html
    │   │   ├── 累積折れ線-横軸_アノテーション数-教師付者用.html
    │   │   ├── 累積折れ線-横軸_タスク数-教師付者用.html
    │   │   └── 累積折れ線-横軸_入力データ数-教師付者用.html
    │   ├── 検査者用
    │   │   ├── 折れ線-横軸_検査開始日-縦軸_アノテーション単位の指標-検査者用.html
    │   │   ├── 折れ線-横軸_検査開始日-縦軸_入力データ単位の指標-検査者用.html
    │   │   ├── 累積折れ線-横軸_アノテーション数-検査者用.html
    │   │   └── 累積折れ線-横軸_入力データ数-検査者用.html
    │   ├── 受入者用
    │   │   ├── 折れ線-横軸_受入開始日-縦軸_アノテーション単位の指標-受入者用.html
    │   │   ├── 折れ線-横軸_受入開始日-縦軸_入力データ単位の指標-受入者用.html
    │   │   ├── 累積折れ線-横軸_アノテーション数-受入者用.html
    │   │   └── 累積折れ線-横軸_入力データ数-受入者用.html
    │   ├── 折れ線-横軸_教師付開始日-全体.html
    │   ├── 折れ線-横軸_日-全体.html
    │   ├── 累積折れ線-横軸_日-縦軸_作業時間.html
    │   └── 累積折れ線-横軸_日-全体.html
    └── scatter
        ├── 散布図-アノテーションあたり作業時間と品質の関係-計測時間-教師付者用.html
        ├── 散布図-アノテーションあたり作業時間と累計作業時間の関係-計測時間.html
        └── 散布図-教師付者の品質と作業量の関係.html



Usage Details
=================================

.. argparse::
   :ref: annofabcli.stat_visualization.write_graph.add_parser
   :prog: annofabcli stat_visualization write_graph
   :nosubcommands:
   :nodefaultconst:

See also
=================================
* `annofabcli statistics visualize <../statistics/visualize.html>`_



