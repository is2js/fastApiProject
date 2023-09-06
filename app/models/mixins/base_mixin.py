from sqlalchemy import PrimaryKeyConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import RelationshipProperty

from app.database.conn import Base
from app.models.utils import class_property


class BaseMixin(Base):
    __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.

    constraint_map = {
        'primary_key': PrimaryKeyConstraint,
        'foreign_key': ForeignKeyConstraint,
        'unique': UniqueConstraint,
    }

    @class_property
    def column_names(cls):
        return cls.__table__.columns.keys()

    @class_property
    def relation_names(cls):
        """
        Users.relation_names
        ['role', 'inviters', 'invitees', 'employee']
        """
        mapper = cls.__mapper__
        # mapper.relationships.items() # ('role', <RelationshipProperty at 0x2c0c8947ec8; role>), ('inviters', <RelationshipProperty at 0x2c0c8947f48; inviters>),
        return [prop.key for prop in mapper.iterate_properties
                if isinstance(prop, RelationshipProperty)]

    @class_property
    def hybrid_property_names(cls):
        """
        Users.hybrid_property_names
        ['is_staff', 'is_chiefstaff', 'is_executive', 'is_administrator', 'is_employee_active', 'has_employee_history']
        """
        mapper = cls.__mapper__
        props = mapper.all_orm_descriptors  # [ hybrid_property  +  InstrumentedAttribute (ColumnProperty + RelationshipProperty) ]
        return [prop.__name__ for prop in props
                if isinstance(prop, hybrid_property)]

    @class_property
    def settable_column_names(cls):
        """"
        pk여부 False + create_at을 제외한 칼럼들의 name
        """
        return [column.name for column in cls.__table__.columns if
                column.primary_key is False and column.name != "created_at"]

    @class_property
    def settable_relation_names(cls):
        """
        Users.settable_relation_names
        ['role', 'inviters', 'invitees', 'employee']
        """
        return [prop for prop in cls.relation_names if getattr(cls, prop).property.viewonly is False]

    @class_property
    def settable_attributes(cls):
        return cls.settable_column_names + cls.settable_relation_names + cls.hybrid_property_names

    def is_setter_or_expression(self, column_name):
        return hasattr(getattr(self.__class__, column_name), 'setter') or \
            hasattr(getattr(self.__class__, column_name), 'expression')

    @class_property
    def constraint_class_list(cls):
        return cls.__table__.constraints

    @classmethod
    def get_constraint_column_names(cls, target):
        """
        :param target: primary_key | foreign_key | unique
        :return: []
        """
        target_constraint_class = cls.constraint_map.get(target)
        target_constraint_class = next(
            (c for c in cls.constraint_class_list if isinstance(c, target_constraint_class)),
            None
        )

        if not target_constraint_class:
            return []

        return target_constraint_class.columns.keys()

    @class_property
    def primary_key_names(cls):
        return cls.get_constraint_column_names('primary_key')

    @class_property
    def foreign_key_names(cls):
        return cls.get_constraint_column_names('foreign_key')

    @class_property
    def unique_names(cls):
        return cls.get_constraint_column_names('unique')