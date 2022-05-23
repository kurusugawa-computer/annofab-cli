====================================================================================
Annofabプロジェクトのアノテーションを編集し、他のプロジェクトで利用する
====================================================================================
AnnofabcliではAnnofabプロジェクト内のアノテーションのエクスポート・インポートが可能です。

本ページではこの機能を利用し、既存のAnnofabプロジェクト内のアノテーションを加工し、他のAnnofabプロジェクトで利用するための方法を記載します。


動作環境
=================================
* annofabcli v1.48.1


作業手順
=================================

既存のAnnofabプロジェクト内のアノテーションをエクスポートする
------------------------------------------------------------------------------

1. `annotation dump <https://annofab-cli.readthedocs.io/ja/latest/command_reference/annotation/dump.html>`_ コマンドを利用してアノテーションをエクスポートします。

.. code-block::

    $ annofabcli annotation dump --project_id prj1 --task_id file://task.txt --output_dir dump-dir/



エクスポートしたアノテーションを加工する
------------------------------------------------------------------------------

1. エクスポートされたアノテーションをコマンド・スクリプト等を用いて加工します。

例:アノテーションを読み込み専用にする場合

.. code-block::

    #!/bin/bash
    from_dir=$1
    to_dir=$2

    mkdir -p "${to_dir}"
    for p in $(find "${from_dir}" -name "*.json"); do
        to_path=$(echo "${p}" | sed "s|${from_dir}|${to_dir}|g")
        mkdir -p "$(dirname "${to_path}")"

        # is_protected を true とすることで読み取り専用にする
        jq '.details[].is_protected|=true' -c "${p}" >"${to_path}"
    done



アノテーションをインポートする
----------------------------------------------------

1. アノテーションのインポートはエクスポート元のプロジェクト・新しく作成したプロジェクト、どちらでも利用することができます。

新しく作成したプロジェクトで利用する場合、エクスポート元のプロジェクトと同一のデータ・タスクが存在する必要があります。
`project copy <https://annofab-cli.readthedocs.io/ja/latest/command_reference/project/copy.html>`_ コマンドを利用して、エクスポート元のプロジェクトをコピーすることで同一のデータ・タスクのプロジェクトを作成できます。

.. code-block::

    $ annofabcli project copy --project_id prj1 --dest_title prj2-title  --dest_project_id prj2 --copy_tasks



2. `annotation restore <https://annofab-cli.readthedocs.io/ja/latest/command_reference/annotation/restore.html>`_ コマンド を利用して、編集したアノテーションをインポートします。

.. code-block::

    $ annofabcli annotation restore --project_id prj2 --annotation dump-dir/




