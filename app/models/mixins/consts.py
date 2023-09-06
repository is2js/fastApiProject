from enum import Enum

from app.models.utils import class_property

OPERATOR_SPLITTER = '__'


class BaseStrEnum(str, Enum):

    @class_property
    def names(cls):
        return [field.name for field in cls]

    @class_property
    def values(cls):
        return [field.value for field in cls]


class Clause(BaseStrEnum):
    WHERE = 'where'
    ORDER_BY = 'order_by'
    HAVING = 'having'
    GROUP_BY = 'group_by'
    JOIN = 'join'
    SELECT = 'select'

    @classmethod
    def extract_from_dict(cls, map_: dict):
        return {key: value for key, value in map_.items() if key in Clause.values}

    @classmethod
    def is_valid_dict(cls, map_: dict):
        return any(clause in Clause.values for clause in map_)


class Logical(BaseStrEnum):
    AND = 'and_'
    OR = 'or_'


if __name__ == '__main__':
    # print([clause.value for clause in Clause])
    # ['where', 'order_by', 'having', 'group_by', 'join', 'select']
    print(Clause.names)
    print(Clause.values)
