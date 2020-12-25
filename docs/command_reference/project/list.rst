=====================
project list
=====================

Description
=================================
プロジェクト一覧を出力します。


Examples
=================================

基本的な使い方
--------------------------

``--organization`` に出力対象のプロジェクトが所属する組織名を指定してください。

以下のコマンドは、組織"org1"配下で、自分が所属しているすべてのプロジェクトを出力します。

.. code-block::

    $ annofabcli project list --organization org1



プロジェクトのタイトルやステータスなどで絞り込み
----------------------------------------------

``--project_query`` を指定すると、プロジェクトのタイトルやステータスなどで絞り込めます。
``--project_query`` に渡す値は、https://annofab.com/docs/api/#operation/getProjectsOfOrganization のクエリパラメータとほとんど同じです。
さらに追加で、``user_id`` , ``except_user_id`` キーも指定できます。


以下のコマンドは、組織"org1"配下で、プロジェクト名に"test"を含むプロジェクト一覧を出力します。

.. code-block::

    $ annofabcli project list --organization org1 --project_query '{"title":"test"}'


組織"org1"配下で、プロジェクトのステータスが「進行中」のプロジェクト一覧を出力します。

.. code-block::

    $ annofabcli project list --organization org1 --project_query '{"status": "active"}'


組織"org1"配下で、ユーザ"user1"がプロジェクトメンバとして参加しているプロジェクトの一覧を出力します。

.. code-block::

    $ annofabcli project list --organization org1 --project_query '{"user_id": "user1"}'


組織"org1"配下で、動画プロジェクトの一覧を出力します。

.. code-block::

    $ annofabcli project list --organization org1 --project_query '{"input_data_type": "movie"}'



所属していないプロジェクトも出力する
----------------------------------------------

``--include_not_joined_project`` を指定すると、所属していないプロジェクトも出力します。
指定しない場合は、所属しているプロジェクトのみ出力します（ ``--project_query '{"user_id":"my_user_id"}'`` と結果は同じ）。


.. code-block::

    $ annofabcli project list --organization org1 --include_not_joined_project



project_idで絞り込み
----------------------------------------------
project_idが ``prj1`` , ``prj2`` であるプロジェクトの一覧を出力します。

.. code-block::

    $ annofabcli project list --project_id prj1 prj2



出力結果
=================================

CSV出力
----------------------------------------------

.. code-block::

    $ annofabcli project list --organization org1 --project_query '{"title":"test"}'


JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli task list --project_id prj1 --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
      {
        "project_id": "prj1",
        "task_id": "task1",
        "phase": "acceptance",
        "phase_stage": 1,
        "status": "complete",
        "input_data_id_list": [
          "input1"
        ],
        "account_id": "12345678-abcd-1234-abcd-1234abcd5678",
        "histories_by_phase": [
          {
            "account_id": "12345678-abcd-1234-abcd-1234abcd5678",
            "phase": "annotation",
            "phase_stage": 1,
            "worked": true,
            "user_id": "test_user_id",
            "username": "test_username"
          },
          ...
        ],
        "work_time_span": 8924136,
        "started_datetime": "2020-11-24T16:21:27.753+09:00",
        "updated_datetime": "2020-11-24T16:29:29.381+09:00",
        "sampling": null,
        "metadata": {},
        "user_id": "test_user_id",
        "username": "test_username",
        "worktime_hour": 2.4789266666666667,
        "number_of_rejections_by_inspection": 0,
        "number_of_rejections_by_acceptance": 1
      },
      ...
    ]


task_idの一覧を出力
----------------------------------------------

.. code-block::

    $ annofabcli task list --project_id prj1 --format task_id_format --output task_id.txt


.. code-block::
    :caption: out.txt

    task1
    task2
    ...