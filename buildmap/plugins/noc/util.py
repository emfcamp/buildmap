import pint

unit = pint.UnitRegistry()
unit.define("decibel = [loss] = dB")


def get_col(row, column, default=None):
    if column in row and row[column] is not None:
        return row[column]
    return default
