==========================================
annotation_specs set_attribute_required
==========================================

Description
=================================
属性を必須にします。
内部的には required の属性制約を追加します。


Examples
=================================

属性名(英語)を指定して、複数属性を必須にする場合
----------------------------------------------

.. code-block::

    $ annofabcli annotation_specs set_attribute_required \
     --project_id prj1 \
     --attribute_name_en color size note


属性名(英語)を記載したファイルを指定して、複数属性を必須にする場合
--------------------------------------------------------------

.. code-block::

    $ annofabcli annotation_specs set_attribute_required \
     --project_id prj1 \
     --attribute_name_en file://attribute_names.txt


Usage Details
=================================

.. argparse::
    :ref: annofabcli.annotation_specs.set_attribute_required.add_parser
    :prog: annofabcli annotation_specs set_attribute_required
    :nosubcommands:
    :nodefaultconst:
