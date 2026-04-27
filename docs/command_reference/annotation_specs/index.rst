==================================================
annotation_specs
==================================================

Description
=================================
アノテーション仕様関係のコマンドです。


Available Commands
=================================


.. toctree::
   :maxdepth: 1
   :titlesonly:

   add_attribute
   add_attribute_restriction
   add_choice_attribute
   add_choices_to_attribute
   add_existing_attribute_to_labels
   add_label
   add_labels
   change_attribute_type
   export
   get_with_attribute_id_replaced_label_name
   get_with_choice_id_replaced_label_name
   get_with_label_id_replaced_label_name
   list_attribute
   list_choice
   list_history
   list_label
   list_label_attribute
   list_attribute_restriction
   list_label_color
   put_label_color
   update_label_field_values


Usage Details
=================================

.. argparse::
   :ref: annofabcli.annotation_specs.subcommand_annotation_specs.add_parser
   :prog: annofabcli annotation_specs
   :nosubcommands:
