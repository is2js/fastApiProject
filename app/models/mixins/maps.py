from sqlalchemy import extract
from sqlalchemy.sql import operators

# operatios에서 지원하지 않은 is, isnot은  isnull이나 eq로 대체한다.
#    op = _operators[op_name]
#    expressions.append(op(column, value))
operator_map = {
    # lambda c,v로 정의하면 => 외부에서는  dict_value( c, v)로 입력해서 호출한다.
    'isnull': lambda c, v: (c == None) if v else (c != None),
    # 추가 => 실패, alias 관계객체 -> alias관계컬럼으로 식을 만들어야하므로 일반적인 create_column 후 getattr is_를 불러오는게 안됨.
    # => is, isnot_은  eq로 처리하면 된다. is_: eq=None /  isnot: ne=None
    # 'is': lambda c, v:  c is v ,
    # 'is_': operators.is_,
    # 'isnot': lambda c, v:  c is not v ,
    # 'exact': operators.eq,
    'eq': operators.eq,
    'ne': operators.ne,  # not equal or is not (for None)

    'gt': operators.gt,  # greater than , >
    'ge': operators.ge,  # greater than or equal, >=
    'lt': operators.lt,  # lower than, <
    'le': operators.le,  # lower than or equal, <=

    'in': operators.in_op,
    'notin': operators.notin_op,
    'between': lambda c, v: c.between(v[0], v[1]),

    'like': operators.like_op,
    'ilike': operators.ilike_op,
    'startswith': operators.startswith_op,
    'istartswith': lambda c, v: c.ilike(v + '%'),
    'endswith': operators.endswith_op,
    'iendswith': lambda c, v: c.ilike('%' + v),
    'contains': lambda c, v: c.ilike('%{v}%'.format(v=v)),

    'year': lambda c, v: extract('year', c) == v,
    'year_ne': lambda c, v: extract('year', c) != v,
    'year_gt': lambda c, v: extract('year', c) > v,
    'year_ge': lambda c, v: extract('year', c) >= v,
    'year_lt': lambda c, v: extract('year', c) < v,
    'year_le': lambda c, v: extract('year', c) <= v,

    'month': lambda c, v: extract('month', c) == v,
    'month_ne': lambda c, v: extract('month', c) != v,
    'month_gt': lambda c, v: extract('month', c) > v,
    'month_ge': lambda c, v: extract('month', c) >= v,
    'month_lt': lambda c, v: extract('month', c) < v,
    'month_le': lambda c, v: extract('month', c) <= v,

    'day': lambda c, v: extract('day', c) == v,
    'day_ne': lambda c, v: extract('day', c) != v,
    'day_gt': lambda c, v: extract('day', c) > v,
    'day_ge': lambda c, v: extract('day', c) >= v,
    'day_lt': lambda c, v: extract('day', c) < v,
    'day_le': lambda c, v: extract('day', c) <= v,
}
