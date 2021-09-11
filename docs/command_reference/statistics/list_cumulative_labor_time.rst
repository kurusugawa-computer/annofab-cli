==========================================
statistics list_cumulative_labor_time
==========================================

Description
=================================

日ごと、フェーズごとの累積作業時間をCSV形式で出力する。





Examples
=================================

基本的な使い方
--------------------------


.. code-block::

    $ annofabcli statistics list_cumulative_labor_time --project_id prj1





出力結果
=================================


.. code-block::

    $ annofabcli statistics list_cumulative_labor_time --project_id prj1 --output out.csv

.. csv-table:: out.csv
   :header: date,phase,worktime_hour


    2020-12-15,acceptance,1.12289361111111
    2020-12-15,annotation,6.67816833333333
    2020-12-16,acceptance,1.72973638888889
    2020-12-16,annotation,13.7682875
    2020-12-17,acceptance,2.6953075
    2020-12-17,annotation,16.3832388888889
    
.. argparse::
   :ref: annofabcli.statistics.list_cumulative_labor_time.add_parser
   :prog: annofabcli statistics list_cumulative_labor_time
   :nosubcommands:
