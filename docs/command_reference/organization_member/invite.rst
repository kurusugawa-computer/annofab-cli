==========================================
organization_member invite
==========================================

Description
=================================
組織にメンバーを招待します。


Examples
=================================


基本的な使い方
--------------------------

対象組織の名前を ``--organization`` に、招待するメンバーのuser_idを ``--user_id`` に、組織メンバーロールを ``--role`` に指定します。


.. code-block::

    $ annofabcli organization_member invite --organization org1 --user_id u1 u2 --role contributor



Usage Details
=================================

.. argparse::
   :ref: annofabcli.organization_member.invite_organization_member.add_parser
   :prog: annofabcli organization_member invite
   :nosubcommands:
   :nodefaultconst:
