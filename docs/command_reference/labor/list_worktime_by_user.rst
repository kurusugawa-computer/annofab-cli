==========================================
labor list_worktime_by_user
==========================================

Description
=================================

ユーザごとに予定作業時間、実績作業時間を出力します。


Examples
=================================

基本的な使い方
--------------------------

集計対象の組織名( ``--organization`` )またはproject_id( ``--project_id`` )を指定して、さらに集計期間を指定してください。
集計期間は日( ``--start_date`` / ``--end_date`` )または月( ``--start_month`` / ``--start_month`` )で指定できます。

以下のコマンドは、組織org1, org2に対して、2019/10/01〜2019/10/31の作業時間を集計します。

.. code-block::

    $ annofabcli labor list_worktime_by_user --organization org1 org2  \
    --start_date 2019-10-01 --end_date 2019-10-31 --output_dir out_dir/


以下のコマンドは、プロジェクトprj11, prj12に対して、2019/10/01〜2019/12/31の作業時間を集計します。

.. code-block::

    $ annofabcli labor list_worktime_by_user --project_id prj1 prj2 \
    --start_month 2019-10 --end_month 2019-12 --output_dir out_dir/


``--user_id`` で集計対象ユーザのuser_idも指定できます。

.. code-block::

    $ annofabcli labor list_worktime_by_user --organization org1 org2  \
    --user_id file://user_id.txt --start_date 2019-10-01 --end_date 2019-10-31 --output_dir out_dir/


集計対象の情報を追加する
--------------------------

``--add_availability`` を指定すれば、ユーザごとの予定稼働時間、 ``--add_monitored_worktime`` を指定すれば計測作業時間も集計します。



出力結果
=================================


.. code-block::

    $ annofabcli labor list_worktime_by_user --organization org1  --output_dir out_dir/ \
    --start_date 2019-10-01 --end_date 2019-10-31 --add_availability --add_monitored_worktime


`out_dir <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/statistics/list_annotation_count/out_dir>`_


.. code-block::

    out_dir/ 
    ├── summary.csv
    ├── 作業時間の詳細一覧.csv
    └── 日ごとの作業時間の一覧.csv


.. warning::

    頻繁に修正しているコマンドのため、予告なく出力内容が変わる可能性があります。


.. argparse::
   :ref: annofabcli.labor.list_worktime_by_user.add_parser
   :prog: annofabcli labor list_worktime_by_user
   :nosubcommands:
