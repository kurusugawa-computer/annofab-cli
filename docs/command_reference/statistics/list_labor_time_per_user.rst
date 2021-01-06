==========================================
statistics list_labor_time_per_user
==========================================

Description
=================================

メンバ別の作業時間、完了数、差し戻し回数を日毎にCSV形式で出力する。






Examples
=================================

基本的な使い方
--------------------------


.. code-block::

    $ annofabcli statistics list_labor_time_per_user --project_id prj1





出力結果
=================================


.. code-block::

    $ annofabcli statistics list_labor_time_per_user --project_id prj1 --output out.csv


`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/master/docs/command_reference/statistics/list_labor_time_per_user/out.csv>`_

各列の詳細を以下に示します。

* worktime_hour: 作業時間[hour]
* tasks_completed: 完了したタスク数
* tasks_rejected: 差し戻された回数

.. warning::

    ``tasks_completed`` , ``tasks_rejected`` は直感的でない数字になる場合があります。信用しないでください。

    
