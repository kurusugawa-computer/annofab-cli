import logging


def set_logger():
    logging_formatter = "%(levelname)-8s : %(asctime)s : %(filename)s : %(name)s : %(funcName)s : %(message)s"
    logging.basicConfig(format=logging_formatter)
    logging.getLogger("annofabapi").setLevel(level=logging.DEBUG)
    logging.getLogger("annofabcli").setLevel(level=logging.DEBUG)
    logging.getLogger("__main__").setLevel(level=logging.DEBUG)
