import typing as tp


class DoubleHandlerRegistration(Exception):
    pass


class BadHandlerSignature(Exception):
    pass


class NotIdentified(Exception):
    pass


class BadRequest(Exception):
    omitted_params: tuple[tp.Tuple[str, tp.Type]]
    mistyped_params: tuple[tp.Tuple[str, tp.Type]]

    def __init__(
        self,
        omitted_params: tp.List[tp.Tuple[str, tp.Type]] = None,
        mistyped_params: tp.List[tp.Tuple[str, tp.Type]] = None,
    ):
        msg = "Bad Request"
        if omitted_params:
            msg += (
                "\nsome params are omitted "
                + f"{', '.join([n + ':' + v.__name__ for n, v in omitted_params])}"
            )
        if mistyped_params:
            msg += (
                "\nsome params are mistyped "
                + f"{', '.join([n + ':' + v.__name__ for n, v in mistyped_params])}"
            )
        super().__init__(msg)
        self.omitted_params = tuple(omitted_params) if omitted_params else tuple()
        self.mistyped_params = tuple(mistyped_params) if mistyped_params else tuple()
