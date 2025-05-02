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



集計期間も指定できます。``--start_date`` は、指定した日付以降に教師付を開始したタスクを集計します。``--end_date`` は、指定した日付以前に更新されたタスクを集計します。


.. code-block::

    $ annofabcli statistics visualize --project_id prj1 --output_dir out_dir \
    --start_date 2020-04-01



タスクの完了条件を指定する
----------------------------------------------
``--task_completion_criteria`` で、集計対象のタスクの完了条件を指定できます。


``acceptance_completed``
~~~~~~~~~~~~~~~~~~~~~~~~~~~


``acceptance_completed`` を指定すると、受入フェーズで完了状態のタスクを「生産したタスク（作業が完了したタスク）」とみなして、受入フェーズ完了状態のタスクを集計対象にします。
デフォルトはこの値です。


``acceptance_reached``
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``acceptance_reached`` を指定すると、受入フェーズに到達したタスクを「生産したタスク（作業が完了したタスク）」とみなして、受入フェーズのタスクを集計対象にします。
受入フェーズをアノテーションチーム以外（たとえばアノテーションを利用するAI開発者など）が作業するときなどに、利用します。

また、以下のCSVとグラフでは、受入フェーズの作業時間と生産量は0になります。
受入フェーズに到達したタスクを「生産したタスク（作業が完了したタスク）」とする場合、受入フェーズの作業は生産量に影響しないためです。

* :doc:`visualize_output_rst/メンバごとの生産性と品質_csv`
* :doc:`visualize_output_rst/日毎の生産量と生産性_csv`
* :doc:`visualize_output_rst/教師付開始日毎の生産量と生産性_csv`
* :doc:`visualize_output_rst/全体の生産性と品質_csv`
* :doc:`visualize_output_rst/折れ線-横軸_日-全体_html`
* :doc:`visualize_output_rst/累積折れ線-横軸_日-全体_html`
* :doc:`visualize_output_rst/折れ線-横軸_教師付開始日-全体_html`





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



生産量のカスタマイズ
=================================

.. _annotation_count_csv:

アノテーション数を変更する
----------------------------------------------
デフォルトでは、アノテーションZIPからアノテーション数を算出します。
しかし、プリアノテーションを用いたプロジェクトなどでは、実際に生産していないプリアノテーションも「アノテーション数」に含まれてしまい、正しい生産性が算出できない場合があります。

``--annotation_count_csv`` に実際に生産したアノテーションの個数が記載CSVファイルを指定することで、正しい生産量と生産性を算出できます。

以下はCSVファイルのサンプルです。

.. code-block::
    :caption: annotation_count.csv

    project_id,task_id,annotation_count
    prj1,task1,10
    prj1,task2,20


CSVには以下の列が存在している必要があります。

* ``project_id``
* ``task_id``
* ``annotation_count``


.. _input_data_count_csv:

入力データ数を変更する
----------------------------------------------
タスクに作業しない参照用のフレームが含まれている場合に有用なオプションです。

``--input_data_count_csv`` に実際に作業したフレーム数（入力データ数）が記載されたCSVファイルを指定します。

以下はCSVファイルのサンプルです。

.. code-block::
    :caption: annotation_count.csv

    project_id,task_id,input_data_count
    prj1,task1,5
    prj1,task2,6


CSVには以下の列が存在している必要があります。

* ``project_id``
* ``task_id``
* ``input_data_count``


.. _custom_project_volume:

独自の生産量を指定する
----------------------------------------------
デフォルトでは、入力データ数とアノテーション数を生産量としています。しかし、この生産量はプロジェクトによっては適切でない場合があります。
たとえば、動画プロジェクトでは動画時間が生産量として適切かもしれません。また、セマンティックセグメンテーションプロジェクトでは塗りつぶしの面積や輪郭線の方が生産量として適切かもしれません。

``--custom_project_volume`` に以下のようなJSON文字列を指定することで、入力データ数とアノテーション数以外の生産量を指定することができます。

.. code-block:: json

    {
      "csv_path": "custom_production_volume.csv", // 生産量が記載されたCSVファイルのパス
      "column_list":[  // 生産量の情報
        {
          "value": "video_duration_minute",  // CSVの列名
          "name": "動画長さ"  // CSVの列名を補足する内容。出力されるグラフなどに用いられる。
        }
      ]
    }


以下は、 ``csv_path`` キーに指定するCSVファイルのサンプルです。

.. code-block::
    :caption: custom_production_volume.csv
        
    project_id,task_id,video_duration_minute
    prj1,task1,10
    prj1,task2,20

CSVには以下の列が存在している必要があります。

* ``project_id``
* ``task_id``
* ``column_list[].value`` で指定した列名



出力結果
=================================

1個のプロジェクトを指定した場合
--------------------------------------------------------------------------------------------

.. code-block::

    $ annofabcli statistics visualize --project_id prj1 --output_dir out_dir --minimal

`out_dir <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/statistics/visualize/out_dir>`_


.. code-block::

    out_dir
    ├── histogram
    │   ├── ヒストグラム-作業時間.html
    │   └── ヒストグラム.html
    ├── project_info.json
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
   visualize_output_rst/教師付開始日毎の生産量と生産性_csv.rst
   visualize_output_rst/全体の生産性と品質_csv.rst
   visualize_output_rst/ユーザ_日付list-作業時間_csv.rst
   visualize_output_rst/task-worktime-list-by-user-phase_csv

   visualize_output_rst/折れ線-横軸_日-全体_html.rst
   visualize_output_rst/累積折れ線-横軸_日-全体_html.rst
   visualize_output_rst/折れ線-横軸_教師付開始日-全体_html.rst
   visualize_output_rst/累積折れ線-横軸_アノテーション数-phase者用_html.rst
   visualize_output_rst/折れ線-横軸_教師付開始日-縦軸_アノテーション単位の指標-phase用.html
   visualize_output_rst/累積折れ線-横軸_日-縦軸_作業時間_html.rst

   visualize_output_rst/散布図-アノテーションあたり作業時間と品質の関係-教師付者用_html.rst
   visualize_output_rst/散布図-アノテーションあたり作業時間と累計作業時間の関係_html.rst
   visualize_output_rst/散布図-教師付者の品質と作業量の関係_html.rst



複数のプロジェクトを指定した場合
--------------------------------------------------------------------------------------------

.. code-block::

    $ annofabcli statistics visualize --project_id prj1 prj2 --output_dir out_dir --minimal

プロジェクトごとにディレクトリが生成されます。ディレクトリ名は project_id です。

.. code-block::

    out_dir/
    ├── project_id1/
    │   ├── タスクlist.csv
    │   ├── メンバごとの生産性と品質.csv
    │   └── ...
    ├── project_id2/
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
    ├── project_id1/
    │   ├── タスクlist.csv
    │   ├── メンバごとの生産性と品質.csv
    │   └── ...
    ├── project_id2/
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

