====================================================================================
stat_visualization write_task_histogram
====================================================================================

Description
=================================
``annofabcli statistics visualize`` コマンドの出力ファイルである ``タスクlist.csv`` から、ヒストグラムを出力します。


Examples
=================================

基本的な使い方
--------------------------

``--csv`` に ``annofabcli statistics visualize`` コマンドの出力ファイル ``タスクlist.csv`` のパスを指定してください。


.. code-block::

    $ annofabcli statistics visualize --project_id prj1 --output_dir prj1_dir/

    $ annofabcli stat_visualization write_task_histogram --csv prj1_dir/タスクlist.csv \
     --output_dir histogram/



出力結果
=================================

.. code-block::

    $ annofabcli stat_visualization write_task_histogram --csv prj1_dir/タスクlist.csv \
     --output_dir histogram/ --minimal

    $ ls -1 histogram/
    ヒストグラム-作業時間.html
    ヒストグラム.html

Usage Details
=================================

.. argparse::
   :ref: annofabcli.stat_visualization.write_task_histogram.add_parser
   :prog: annofabcli stat_visualization write_task_histogram
   :nosubcommands:
   :nodefaultconst:


See also
=================================
* `annofabcli statistics visualize <../statistics/visualize.html>`_

