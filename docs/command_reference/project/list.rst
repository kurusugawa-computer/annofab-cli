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
-------------------------------------------------------

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

    $ annofabcli project list --organization org1 --format csv --output out.csv

`out.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/project/list/out.csv>`_


最小限の列のみ出力する場合は、``--format minimal_csv`` を指定してください。

.. code-block::

    $ annofabcli project list --organization org1 --format minimal_csv --output out_minimal.csv

`out_minimal.csv <https://github.com/kurusugawa-computer/annofab-cli/blob/main/docs/command_reference/project/list/out_minimal.csv>`_



JSON出力
----------------------------------------------

.. code-block::

    $ annofabcli project list --organization org1 --format pretty_json --output out.json



.. code-block::
    :caption: out.json

    [
      {
        "project_id": "prj1",
        "organization_id": "org1",
        "title": "test-project",
        "overview": "",
        "project_status": "suspended",
        "input_data_type": "image",
        "created_datetime": "2020-03-30T13:15:01.903+09:00",
        "updated_datetime": "2020-12-17T13:49:37.564+09:00",
        "configuration": {
          "number_of_inspections": 1,
          "assignee_rule_of_resubmitted_task": "no_assignee",
          "task_assignment_type": "random",
          "max_tasks_per_member": 30,
          "max_tasks_per_member_including_hold": 30,
          "private_storage_aws_iam_role_arn": null,
          "plugin_id": null,
          "custom_task_assignment_plugin_id": null,
          "custom_specs_plugin_id": null,
          "input_data_set_id_list": null,
          "input_data_max_long_side_length": null,
          "sampling_inspection_rate": 50,
          "sampling_acceptance_rate": 0,
          "editor_version": "stable"
        },
        "summary": {
          "last_tasks_updated_datetime": "2020-11-11T18:06:58.642+09:00"
        },
        "organization_name": "test-organization"
      }
    ]




project_idの一覧を出力
----------------------------------------------

.. code-block::

    $ annofabcli project list --organization org1 --format project_id_list --output out.txt


.. code-block::
    :caption: out.txt

    prj1
    prj2
    ...

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project.list_project.add_parser
   :prog: annofabcli project list
   :nosubcommands:
   :nodefaultconst:
