=================================
project change_organization
=================================

Description
=================================
プロジェクトの所属先組織を変更します。


Examples
=================================


.. code-block::

    $ annofabcli project change_organization --project_id prj1 prj2 --organization org1


デフォルトでは、「進行中」状態のプロジェクトの組織を変更できません。
「進行中」状態のプロジェクトの組織を変更するには、 ``--force`` を指定してください。「停止中」状態にした後、プロジェクトを変更します。


Usage Details
=================================

.. argparse::
   :ref: annofabcli.project.change_organization_of_project.add_parser
   :prog: annofabcli project change_organization
   :nosubcommands:
   :nodefaultconst:
