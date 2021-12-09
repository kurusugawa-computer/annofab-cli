====================================================================================
stat_visualization write_linegraph_per_user
====================================================================================

Description
=================================
``annofabcli statistics visualize`` コマンドの出力ファイル ``タスクlist.csv`` から、ユーザごとの指標をプロットした折れ線グラフを出力します。


Examples
=================================

基本的な使い方
--------------------------

``--csv`` に ``annofabcli statistics visualize`` コマンドの出力ファイル ``タスクlist.csv`` のパスを指定してください。



.. code-block::

    $ annofabcli statistics visualize --project_id prj1 --output_dir prj1_dir/
    
    $ annofabcli stat_visualization write_linegraph_per_user --csv prj1_dir/タスクlist.csv \
     --output_dir line-graph/


折れ線グラフにプロットするユーザを指定する場合は、``--user_id`` にプロットするユーザのuser_idを指定してください。

.. code-block::

    $ annofabcli stat_visualization write_linegraph_per_user --csv prj1_dir/タスクlist.csv \
     --output_dir line-graph/ --user_id user1 user2 user3


出力結果
=================================

.. code-block::

    $ annofabcli stat_visualization write_linegraph_per_user --csv prj1_dir/タスクlist.csv \
     --output_dir line-graph/ --minimal

    $ ls -1 line-graph/
    累積折れ線-横軸_アノテーション数-教師付者用.html
    累積折れ線-横軸_アノテーション数-受入者用.html

Usage Details
=================================

.. argparse::
   :ref: annofabcli.stat_visualization.write_linegraph_per_user.add_parser
   :prog: annofabcli stat_visualization write_linegraph_per_user
   :nosubcommands:
   :nodefaultconst:

See also
=================================
* `annofabcli statistics visualize <../statistics/visualize.html>`_

