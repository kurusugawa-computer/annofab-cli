=====================
labor list_worktime_by_user
=====================

Description
=================================

ユーザごとに予定作業時間、実績作業時間を出力します。



### labor list_worktime_by_user

ユーザごとに作業予定時間、作業実績時間を出力します。

```
# 組織org1, org2に対して、user1, user2の作業時間を集計します。
$ annofabcli labor list_worktime_by_user --organization org1 org2 --user_id user1 user2 \
 --start_date 2019-10-01 --end_date 2019-10-31 --output_dir /tmp/output

# プロジェクトprj1, prj2に対して作業時間を集計します。集計対象のユーザはプロジェクトに所属するメンバです。
$ annofabcli labor list_worktime_by_user --project_id prj1 prj2 --user_id user1 user2 \
 --start_date 2019-10-01 --end_date 2019-10-31 --output_dir /tmp/output


# user.txtに記載されているユーザの予定稼働時間も一緒に出力します。
$ annofabcli labor list_worktime_by_user --project_id prj1 dprj2 --user_id file://user.txt \
 --start_month 2019-10 --end_month 2019-11 --add_availability --output_dir /tmp/output

```



optional arguments:
  -h, --help            show this help message and exit
  -org ORGANIZATION [ORGANIZATION ...], --organization ORGANIZATION [ORGANIZATION ...]
                        集計対象の組織名を指定してください。`file://`を先頭に付けると、組織名の一覧が記載されたファイルを指定できます。 (default: None)
  -p PROJECT_ID [PROJECT_ID ...], --project_id PROJECT_ID [PROJECT_ID ...]
                        集計対象のプロジェクトを指定してください。`file://`を先頭に付けると、project_idの一覧が記載されたファイルを指定できます。 (default: None)
  -u USER_ID [USER_ID ...], --user_id USER_ID [USER_ID ...]
                        集計対象のユーザのuser_idを指定してください。`--organization`を指定した場合は必須です。指定しない場合は、プロジェクトメンバが指定されます。`file://`を先頭に付けると、user_idの一覧が記載されたファイルを指定できます。 (default: None)
  --add_availability    指定した場合、'ユーザごとの作業時間.csv'に予定稼働時間も出力します。 (default: False)
  --add_monitored_worktime
                        指定した場合、'作業時間の詳細一覧.csv'にAnnoFab計測時間も出力します。 (default: False)
  --start_date START_DATE
                        集計期間の開始日(YYYY-MM-DD) (default: None)
  --start_month START_MONTH
                        集計期間の開始月(YYYY-MM-DD) (default: None)
  --end_date END_DATE   集計期間の終了日(YYYY-MM) (default: None)
  --end_month END_MONTH
                        集計期間の終了月(YYYY-MM) (default: None)
  -o OUTPUT_DIR, --output_dir OUTPUT_DIR





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

