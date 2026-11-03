"""スレッド間で処理の中断を伝えるための共通処理。"""

from threading import Event


class Cancellation:
    """中断要求を共有し、処理の区切りでKeyboardInterruptを送出します。"""

    def __init__(self) -> None:
        self._event = Event()
        """中断が要求されたかどうか。"""

    def cancel(self) -> None:
        """中断を要求します。

        Args:
            なし。

        Returns:
            None。
        """
        self._event.set()

    def check(self) -> None:
        """中断要求があればKeyboardInterruptを送出します。

        Args:
            なし。

        Returns:
            None。
        """
        if self._event.is_set():
            raise KeyboardInterrupt

    def wait(self, seconds: float) -> None:
        """指定時間待ち、中断要求があれば直ちにKeyboardInterruptを送出します。

        Args:
            seconds: 待機時間（秒）。

        Returns:
            None。
        """
        if self._event.wait(seconds):
            raise KeyboardInterrupt
