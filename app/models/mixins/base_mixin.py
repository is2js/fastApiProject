from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import RelationshipProperty

from app.database.conn import Base
from app.models.utils import class_property


class BaseMixin(Base):
    __abstract__ = True  # Base상속이면서, tablename 자동화할려면 필수.

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
