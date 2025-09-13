=================================
project update
=================================

Description
=================================
プロジェクトのタイトルまたは概要を更新します。


Examples
=================================




CSVファイルを指定する場合
--------------------------------------
``--csv`` に、更新対象のプロジェクト情報が記載されたCSVファイルのパスを指定してください。

CSVのフォーマットは以下の通りです。

* カンマ区切り
* ヘッダ行あり

.. csv-table::
   :header: 列名,必須,備考

    project_id,Yes,更新対象のプロジェクトID
    title,No,変更後のプロジェクトタイトル。更新しない場合は空欄
    overview,No,変更後のプロジェクト概要。更新しない場合は空欄


以下はCSVファイルのサンプルです。

.. code-block::
    :caption: project.csv

    project_id,title,overview
    prj1,新しいタイトル1,新しい概要1
    prj2,,変更された概要のみ
    prj3,タイトルのみ変更,


.. code-block::

    $ annofabcli project update --csv project.csv




JSON文字列を指定する場合
--------------------------------------
``--json`` に、更新対象のプロジェクト情報をJSON文字列で指定してください。

以下は、JSONのサンプルです。

.. code-block::
    :caption: project.json

    [
        {
            "project_id": "prj1",
            "title": "新しいタイトル1",
            "overview": "新しい概要1"
        },
        {
            "project_id": "prj2",
            "overview": "変更された概要のみ"
        },
        {
            "project_id": "prj3",
            "title": "タイトルのみ変更"
        }
    ]

JSONのキーは、 ``--csv`` に指定するCSVファイルの列に対応します。
更新しないプロパティは、キーを記載しないか値をnullにしてください。

``--json`` にJSON形式の文字列、またはJSONファイルのパスを指定できます。

.. code-block::

    $ annofabcli project update --json file://project.json



複数のプロジェクトにプレフィックスを付与する場合
--------------------------------------------------
複数のプロジェクトのタイトルに一律でプレフィックスを付与したい場合などに便利です。

.. code-block::
    :caption: プレフィックス付与用のproject.json

    [
        {
            "project_id": "prj1",
            "title": "[2024年度] 既存プロジェクト1"
        },
        {
            "project_id": "prj2", 
            "title": "[2024年度] 既存プロジェクト2"
        }
    ]

.. code-block::

    $ annofabcli project update --json file://project.json --yes



並列処理を使用する場合
--------------------------------------
``--parallelism`` オプションを使用すると、複数のプロジェクトを並列で更新できます。
大量のプロジェクトを更新する際に処理時間を短縮できます。

.. code-block::

    $ annofabcli project update --csv project.csv --parallelism 2 --yes


.. note::

    ``--parallelism`` を指定する場合は、必ず ``--yes`` も指定する必要があります。




Usage Details
=================================

.. argparse::
   :ref: annofabcli.project.update_project.add_parser
   :prog: annofabcli project update
   :nosubcommands:
   :nodefaultconst:
