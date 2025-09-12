=================================
project update_configuration
=================================

Description
=================================
複数のプロジェクトの設定を一括で更新します。
既存の設定に対して部分的な更新を行います（設定の完全な置き換えではありません）。


Examples
=================================

以下のコマンドは、プロジェクトp1,p2に対して、アノテーションエディタのバージョンをプレビュー版に更新します。

.. code-block::

    $ annofabcli project update_configuration --project_id p1 p2 \
     --configuration '{"editor_version":"preview"}'

``--configuration`` のJSON構造は、 `putProject <https://annofab.com/docs/api/#operation/putProject>`_ APIのリクエストボディの ``configuration`` と同じです。


よく利用するであろう ``--configuration`` の例を以下のJSONに記載します。


.. code-block:: 
        
    {
        # アノテーションエディタのバージョンをプレビュー版
        "editor_version":"preview",
        
        # 保留中のタスクを除き、1人（オーナー以外）に割り当てられるタスク数の上限
        "max_tasks_per_member": 100,
        
        # 保留中のタスクを含めて、1人（オーナー以外）に割り当てられるタスク数上限
        "max_tasks_per_member_including_hold": 100,
        
        # S3プライベートストレージ認可用AWS IAMロールARN
        "private_storage_aws_iam_role_arn": "arn:aws:iam::123456789012:role/YourRoleName",
    }
    

Usage Details
=================================

.. argparse::
   :ref: annofabcli.project.update_configuration.add_parser
   :prog: annofabcli project update_configuration
   :nosubcommands:
   :nodefaultconst:
