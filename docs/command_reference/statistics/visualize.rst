=====================
statistics visualize
=====================

Description
=================================

生産量や生産性に関するCSVファイルやグラフを出力します。

出力結果から主に以下のことが分かります。

* 生産量や生産性の日ごとの推移
* ユーザごとの生産性と品質





Examples
=================================

基本的な使い方
--------------------------

出力対象のプロジェクトのproject_idを指定してください。複数のプロジェクトを指定することも可能です。

.. code-block::

    $ annofabcli statistics visualize --project_id prj1 --output_dir out_dir

集計対象のタスクの条件を ``--task_query`` で指定してください。

.. code-block::

    $ annofabcli statistics visualize --project_id prj1 --output_dir out_dir
    --task_query '{"status": "complete"}' 

.. note::

    できるだけ正しい生産性を求める場合は、``--task_query '{"status": "complete"}'`` を指定して、完了状態のタスクのみを集計対象としてください。
    デフォルトでは完了状態でないタスクも「生産した」とみなします。


集計期間も指定できます。``--start_date`` は、指定した日付以降に教師付を開始したタスクを集計します。``--end_date`` は、指定した日付以前に更新されたタスクを集計します。


.. code-block::

    $ annofabcli statistics visualize --project_id prj1 --output_dir out_dir \
    --start_date 2020-04-01


デフォルトでは10個以上のファイルを出力します。よく利用するファイルのみ出力する場合は、 ``--minimal`` を指定してください。

.. code-block::

    $ annofabcli input_data put --project_id prj1 --output out_dir/
    --minimal


実績作業時間情報から生産性を算出する
----------------------------------------------
デフォルトではアノテーションエディタ画面を触っていた作業時間（以下、「計測作業時間」と呼ぶ）を元に、生産性を算出します。
計測作業時間はコミュニケーションしている時間やアノテーションルールを読んでいる時間を含みません。
したがって、計測作業時間から算出した生産性を元にアノテーションの生産量を見積もると、見積もりから大きく外れる恐れがあります。

アノテーションの生産量を見積もる場合は、アノテーションエディタ以外の作業も含めた作業時間（以下、「実績作業時間」と呼ぶ）で生産性を算出することを推奨します。
実績作業時間から算出した生産性を出力するには、実績作業時間が記載されたCSVを ``--labor_csv`` に渡してください。

.. code-block::

    $ annofabcli input_data put --project_id prj1 --labor_csv labor.csv \
    --output out_dir/


以下、実績作業時間が記載されたCSV( ``labor.csv`` )のサンプルです。

.. csv-table::
   :header: date,account_id,actual_worktime_hour,project_id

    2021-04-01,12345678-abcd-1234-abcd-1234abcd5678,8,prj1
    2021-04-02,12345678-abcd-1234-abcd-1234abcd5678,6.5,prj1


.. warning::

    2021-10-01 時点で、AnnoFabに実績作業時間を格納することができます。AnnoFabに可能されている実績作業時間を参照する場合は、``--get_labor`` を指定してください。
    ただし、``--get_labor`` は将来的に廃止します。AnnoFabには実績作業時間は、いずれ参照できなくなるためです。
    替わりに ``--labor_csv`` を利用してください。
    







複数のプロジェクトをマージする
----------------------------------------------
``--project_id`` に複数のproject_idを指定したときに ``--merge`` を指定すると、指定したプロジェクトをマージしたディレクトリも出力します。ディレクトリ名は ``merge`` です。

.. code-block::

    $ annofabcli input_data put --project_id prj1 prj2 --output out_dir/
    --merge



並列処理
----------------------------------------------

``--project_id`` に複数のproject_idを指定したときは、並列実行が可能です。

.. code-block::

    $ annofabcli input_data put --project_id file://project_id.txt --output out_dir/
    --parallelism 4





出力結果
=================================

1個のプロジェクトを指定した場合
--------------------------------------------------------------------------------------------

.. code-block::

    $ annofabcli statistics visualize --project_id prj1 --output_dir out_dir --minimal

`out_dir <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/statistics/visualize/out_dir>`_


.. code-block::

    out_dir
    ├── histogram
    │   ├── ヒストグラム-作業時間.html
    │   └── ヒストグラム.html
    ├── ${project_title}.json
    ├── line-graph
    │   ├── 教師付者用
    │   │   └── 累積折れ線-横軸_アノテーション数-教師付者用.html
    │   ├── 受入者用
    │   │   └── 累積折れ線-横軸_アノテーション数-受入者用.html
    │   ├── 折れ線-横軸_教師付開始日-全体.html
    │   ├── 折れ線-横軸_日-全体.html
    │   ├── 累積折れ線-横軸_日-縦軸_作業時間.html
    │   └── 累積折れ線-横軸_日-全体.html
    ├── scatter
    │   ├── 散布図-アノテーションあたり作業時間と品質の関係-計測時間-教師付者用.html
    │   ├── 散布図-アノテーションあたり作業時間と累計作業時間の関係-計測時間.html
    │   ├── 散布図-アノテーションあたり作業時間と品質の関係-実績時間-教師付者用.html
    │   ├── 散布図-アノテーションあたり作業時間と累計作業時間の関係-実績時間.html
    │   └── 散布図-教師付者の品質と作業量の関係.html
    ├── タスクlist.csv
    ├── メンバごとの生産性と品質.csv
    ├── ユーザ_日付list-作業時間.csv
    ├── 教師付開始日毎の生産量と生産性.csv
    ├── 全体の生産性と品質.csv
    └── 日毎の生産量と生産性.csv





.. toctree::
   :maxdepth: 1
   :titlesonly:


   visualize_output_rst/タスクlist_csv.rst
   visualize_output_rst/メンバごとの生産性と品質_csv.rst
   visualize_output_rst/日毎の生産量と生産性_csv.rst
   visualize_output_rst/全体の生産性と品質_csv.rst
   visualize_output_rst/ユーザ_日付list-作業時間_csv.rst

   visualize_output_rst/折れ線-横軸_日-全体_html.rst
   visualize_output_rst/累積折れ線-横軸_日-全体_html.rst
   visualize_output_rst/折れ線-横軸_教師付開始日-全体_html.rst
   visualize_output_rst/累積折れ線-横軸_アノテーション数-phase者用_html.rst
   visualize_output_rst/累積折れ線-横軸_日-縦軸_作業時間_html.rst

   visualize_output_rst/散布図-アノテーションあたり作業時間と品質の関係-教師付者用_html.rst
   visualize_output_rst/散布図-アノテーションあたり作業時間と累計作業時間の関係_html.rst
   visualize_output_rst/散布図-教師付者の品質と作業量の関係_html.rst



複数のプロジェクトを指定した場合
--------------------------------------------------------------------------------------------

.. code-block::

    $ annofabcli statistics visualize --project_id prj1 prj2 --output_dir out_dir --minimal

プロジェクトごとにディレクトリが生成されます。

.. code-block::

    out_dir/
    ├── prj_title1
    │   ├── タスクlist.csv
    │   ├── メンバごとの生産性と品質.csv
    │   └── ...
    ├── prj_title2
    │   ├── タスクlist.csv
    │   ├── メンバごとの生産性と品質.csv
    │   └── ...



``--merge`` を指定した場合
--------------------------------------------------------------------------------------------

.. code-block::

    $ annofabcli statistics visualize --project_id prj1 prj2 --output_dir out_dir --minimal \
    --merge

prj1とprj2の出力結果をマージしたファイルが、``merge`` ディレクトリに出力されます。

.. code-block::

    out_dir/
    ├── prj_title1
    │   ├── タスクlist.csv
    │   ├── メンバごとの生産性と品質.csv
    │   └── ...
    ├── prj_title2
    │   ├── タスクlist.csv
    │   ├── メンバごとの生産性と品質.csv
    │   └── ...
    ├── merge
    │   ├── タスクlist.csv
    │   ├── メンバごとの生産性と品質.csv
    │   └── ...

Usage Details
=================================

.. argparse::
   :ref: annofabcli.statistics.visualize_statistics.add_parser
   :prog: annofabcli statistics visualize
   :nosubcommands:
   :nodefaultconst:
