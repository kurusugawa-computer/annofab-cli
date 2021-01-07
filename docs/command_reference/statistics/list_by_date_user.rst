==========================================
statistics list_by_date_user
==========================================

Description
=================================

タスク数や作業時間などの情報を、日ごとユーザごとに出力します。



Examples
=================================

基本的な使い方
--------------------------

タスク履歴全件ファイルから、CSVファイルを出力します。

.. code-block::

    $ annofabcli statistics list_by_date_user --project_id prj1

集計期間を指定することも可能です。

.. code-block::

    $ annofabcli statistics list_by_date_user --project_id prj1 \
    --start_date 2020-01-01 --end_date 2020-01-31




出力結果
=================================


.. code-block::

    $ annofabcli statistics list_by_date_user --project_id prj1 --output out.csv


`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/statistics/list_by_date_user/out.csv>`_

