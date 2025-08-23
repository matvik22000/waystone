import os
import sys
from dataclasses import dataclass
from logging import getLogger
from typing import Any


@dataclass
class Config:
    def __post_init__(self):
        suspicious_variables = []
        for variable, value in vars(type(self)).items():
            if (
                not variable.startswith("__")
                and not self.__annotations__.get(variable)
                and isinstance(value, Field)
            ):
                suspicious_variables.append(variable)
        if suspicious_variables:
            raise Exception(
                f"{suspicious_variables} are specified as fields, bot haven't got types. "
                f"Correct syntax is: some_variable: int = optional(10) "
                f"or some_variable: str = required()"
            )

        not_presented = []
        not_uppercase = []
        for variable, tp in self.__annotations__.items():
            field = getattr(self, variable)

            if not variable.isupper():
                not_uppercase.append(variable)
                fromEnv = os.environ.get(variable.upper(), None)
            else:
                fromEnv = os.environ.get(variable, None)

            if fromEnv is None and field.required:
                not_presented.append(variable)
            try:
                convertedValue = tp(fromEnv or field.default)
                setattr(self, variable, convertedValue)
            except TypeError:
                raise Exception(
                    f"{variable}: expected {tp}, found in env {fromEnv}, default {field.default}"
                )

        if not_uppercase:
            getLogger().warning(
                "All env variable names should be uppercase. %s were implicitly casted to uppercase",
                not_uppercase,
            )

        if not_presented:
            raise Exception(
                f"Required values are not presented in environ: {not_presented}"
            )

        getLogger().info("Config loaded: %s", str(self))

    def __str__(self):
        return (
            "Config("
            + ", ".join(
                [
                    f"{entry[0]}={str(entry[1])}"
                    for entry in filter(lambda s: True, vars(self).items())
                ]
            )
            + ")"
        )


@dataclass
class Field:
    default: Any
    required: bool


def optional(default=None):
    return Field(default, False)


def required():
    return Field(None, True)
